"""Biblioteca de Soluções de Impacto: cadastro, perfil com proveniência, busca por intenção, comparação, adaptação, combinação, match e recomendações.

Regras de verdade: ideia ≠ case; autodeclarado ≠ comprovado (nível de confiança só muda pela administração); resultados "reportados" ≠ "validados";
visualização ≠ intenção; plano/assinatura nunca influenciam busca, match ou recomendação."""
from __future__ import annotations

from ..db.pq import Json
from ..engines.institutional import intent as inst_intent
from ..engines.institutional import readiness
from ..engines.match import solution as solution_match
from ..engines.solutions import adaptation as adapt_engine
from ..engines.solutions import combine as combine_engine
from ..engines.solutions import concepts as K
from ..engines.solutions import intent as I
from ..engines.solutions import scoring as SC
from ..http import ApiError, Ctx, not_found, page, route
from ..services import catalog
from ..services import institutional as inst_svc
from ..services import solutions as svc
from . import schemas as S

T = ("solutions",)
AUTHOR_KINDS = ("osc", "individual", "company", "government", "provider")
NOT_NULL = {"stage", "title", "summary", "license", "allow_replication", "allow_adaptation", "attribution_required", "seeking_funding", "raised_cents",
            "themes", "population", "institutions", "ods", "esg", "goals", "schedule", "source_type", "ownership_type", "confidentiality",
            "authorization_publish", "authorization_contact", "compatible_modalities"}
ARRAYS = {"themes": "text[]", "population": "text[]", "institutions": "text[]", "ods": "smallint[]", "esg": "text[]", "compatible_modalities": "text[]"}
JSONS = {"goals", "schedule"}


def _validate_vocab(d: dict) -> None:
    bad = [t for t in d.get("themes") or [] if t not in catalog.CAUSES]
    if bad:
        raise ApiError(422, "validation_error", "Temas fora da taxonomia: " + ", ".join(bad), {"valid": sorted(catalog.CAUSES)})
    cfg = K.load()["concepts"]
    for field, dim in (("population", "population"), ("institutions", "institution")):
        bad = [t for t in d.get(field) or [] if t not in cfg or cfg[t]["dim"] != dim]
        if bad:
            raise ApiError(422, "validation_error", f"Valores inválidos em {field}: " + ", ".join(bad),
                           {"valid": sorted(k for k, v in cfg.items() if v["dim"] == dim)})


IP_FIELDS = {"rights_holder", "ownership_type", "confidentiality", "authorization_publish", "license", "ip_notes", "usage_conditions"}


def _validate_modalities(c, d: dict) -> None:
    mods = d.get("compatible_modalities") or []
    if mods:
        known = inst_svc.catalog(c, "funding_modality").get("funding_modality", {})
        bad = [m for m in mods if m not in known]
        if bad:
            raise ApiError(422, "validation_error", "Modalidades fora do catálogo publicado: " + ", ".join(bad), {"valid": sorted(known)})


def _validate_consistency(d: dict) -> None:
    if (d.get("allow_replication") or d.get("allow_adaptation")) and d.get("license") == "all_rights_reserved":
        raise ApiError(422, "license_conflict", "Para permitir replicação ou adaptação, escolha uma licença que a autorize (ex.: CC BY) ou 'custom' com condições de uso.")
    if d.get("kind") == "idea" and d.get("stage") not in (None, "idea", "proposal"):
        raise ApiError(422, "idea_stage", "Uma ideia só pode estar nos estágios 'ideia' ou 'proposta' — ideia não é case executado.")
    if d.get("seeking_funding") and d.get("needed_cents") is None:
        raise ApiError(422, "needed_required", "Informe o valor necessário para marcar a solução como em busca de financiamento.")
    if d.get("period_start") and d.get("period_end") and d["period_end"] < d["period_start"]:
        raise ApiError(422, "period_invalid", "O fim do período não pode ser anterior ao início.")


def _owned(c, ctx, sid: str, *, lock: bool = False) -> dict:
    r = c.one("SELECT id::text AS id, kind, stage, visibility, license, allow_replication, allow_adaptation, seeking_funding, needed_cents, budget_cents, raised_cents,"
              " generated_draft, human_reviewed_at, trust_level, themes, title, summary, problem, approach, objectives, ownership_type, confidentiality,"
              " authorization_publish, compatible_modalities FROM solutions WHERE id = $1 AND org_id = $2"
              + (" FOR UPDATE" if lock else ""), sid, ctx.org_id)
    if not r:
        raise not_found("Solução")
    return r


def _readable(c, sid: str) -> dict:
    r = svc.get_solution(c, sid)
    if not r:
        raise not_found("Solução")
    return r


# ------------------------------------------------------------------------------------------------ cadastro
@route("POST", "/v1/solutions", body=S.SolutionIn, kinds=AUTHOR_KINDS, min_role="member", status=201, tags=T,
       summary="Cadastra uma solução (nasce como rascunho, autodeclarada e não verificada)")
def create(ctx: Ctx, body: S.SolutionIn):
    d = body.model_dump()
    _validate_vocab(d)
    _validate_consistency(d)
    with ctx.tx() as c:
        if d.get("project_id") and not c.one("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", d["project_id"], ctx.org_id):
            raise not_found("Projeto")
        _validate_modalities(c, d)
        cols = list(d)
        sql = ("INSERT INTO solutions(org_id, created_by, " + ", ".join(cols) + ") VALUES ($1, $2, " +
               ", ".join(f"${i + 3}" + ("::" + ARRAYS[k] if k in ARRAYS else "::jsonb" if k in JSONS else "") for i, k in enumerate(cols)) + ") RETURNING id::text")
        sid = c.scalar(sql, ctx.org_id, ctx.user_id, *[Json(d[k]) if k in JSONS else d[k] for k in cols])
        if IP_FIELDS & {k for k in cols if d[k] not in (None, "unknown", "public", False, "all_rights_reserved")}:
            c.run("UPDATE solutions SET ip_declared_at = now(), ip_declared_by = $2 WHERE id = $1", sid, ctx.user_id)
        ctx.audit(c, "solution.created", "solution", sid, {"kind": d["kind"], "stage": d["stage"]})
    return {"id": sid, "visibility": "draft", "trust": SC.TRUST_LABEL["self_declared"]}


@route("GET", "/v1/solutions/mine", min_role="viewer", query=S.Pagination, tags=T, summary="Soluções da minha organização (inclui rascunhos)")
def mine(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {svc.CARD_COLS} FROM solutions s WHERE s.org_id = $1 AND s.visibility <> 'removed' ORDER BY s.updated_at DESC LIMIT $2 OFFSET $3",
                       ctx.org_id, q.limit + 1, q.offset)
        feats = svc.features(c, [r["id"] for r in rows[:q.limit]])
        items = [svc.public_card(r, svc.scores_for(r, feats[r["id"]]), mine=True) | {"generated_draft": r.get("generated_draft")} for r in rows[:q.limit]]
    return page(items + ([{}] if len(rows) > q.limit else []), q.limit, q.offset)


@route("PATCH", "/v1/solutions/{solution_id}", body=S.SolutionPatch, kinds=AUTHOR_KINDS, min_role="member", tags=T,
       summary="Edita a solução (gera nova versão; mudança substantiva de conteúdo verificado volta para 'em revisão')")
def patch(ctx: Ctx, body: S.SolutionPatch):
    d = body.model_dump(exclude_unset=True)
    if not d:
        raise ApiError(422, "empty_patch", "Nenhum campo informado")
    for k in d:
        if d[k] is None and k in NOT_NULL:
            raise ApiError(422, "validation_error", f"'{k}' não pode ser nulo")
    _validate_vocab(d)
    with ctx.tx() as c:
        cur = _owned(c, ctx, ctx.path["solution_id"], lock=True)
        if cur["visibility"] == "removed":
            raise ApiError(409, "removed", "Solução removida pela administração")
        merged = {**cur, **d}
        _validate_consistency(merged)
        _validate_modalities(c, d)
        sets, args = [], []
        for k, v in d.items():
            args.append(Json(v) if k in JSONS else v)
            sets.append(f"{k} = ${len(args)}" + ("::" + ARRAYS[k] if k in ARRAYS else "::jsonb" if k in JSONS else ""))
        if IP_FIELDS & set(d):  # declaração de propriedade intelectual carimba quem declarou e quando
            args.append(ctx.user_id)
            sets.append(f"ip_declared_at = now(), ip_declared_by = ${len(args)}")
        args.append(cur["id"])
        before = cur["trust_level"]
        c.run(f"UPDATE solutions SET {', '.join(sets)} WHERE id = ${len(args)}", *args)
        after = c.scalar("SELECT trust_level FROM solutions WHERE id = $1", cur["id"])
        ctx.audit(c, "solution.updated", "solution", cur["id"], {"fields": sorted(d)})
    return {"id": cur["id"], "trust_level": after, "verification_reset": before != after}


@route("POST", "/v1/solutions/{solution_id}/publish", kinds=AUTHOR_KINDS, min_role="admin", tags=T, summary="Publica a solução na biblioteca (valida o mínimo de conteúdo)")
def publish(ctx: Ctx):
    with ctx.tx() as c:
        s = _owned(c, ctx, ctx.path["solution_id"], lock=True)
        if s["visibility"] == "removed":
            raise ApiError(409, "removed", "Solução removida pela administração")
        gaps = []
        if not s["themes"]:
            gaps.append("Informe ao menos um tema")
        if not (s["problem"] or s["approach"]):
            gaps.append("Descreva o problema ou a abordagem")
        if s["seeking_funding"] and s["needed_cents"] is None:
            gaps.append("Informe o valor necessário")
        if s["generated_draft"] and not s["human_reviewed_at"]:
            gaps.append("Rascunho gerado: confirme a revisão humana antes de publicar")
        if s["ownership_type"] == "unknown":
            gaps.append("Informe a titularidade da propriedade intelectual (autor, organização, coautoria, instituição ou terceiro)")
        if not s["authorization_publish"]:
            gaps.append("Confirme que você tem autorização para publicar este conteúdo (direitos e, se houver, consentimento de terceiros)")
        if gaps:
            raise ApiError(422, "not_publishable", "A solução ainda não pode ser publicada", {"missing": gaps})
        c.run("UPDATE solutions SET visibility = 'published' WHERE id = $1", s["id"])
        ctx.audit(c, "solution.published", "solution", s["id"], {"confidentiality": s["confidentiality"]})
    out = {"id": s["id"], "visibility": "published", "confidentiality": s["confidentiality"],
           "notice": "A plataforma não verifica a titularidade declarada nem concede licença além da escolhida por você; você responde pela autorização informada."}
    if s["confidentiality"] == "confidential":
        out["warning"] = "Conteúdo confidencial: não aparece para outras organizações nem em buscas."
    return out


@route("POST", "/v1/solutions/{solution_id}/archive", kinds=AUTHOR_KINDS, min_role="admin", tags=T, summary="Retira a solução da biblioteca (arquiva)")
def archive(ctx: Ctx):
    with ctx.tx() as c:
        s = _owned(c, ctx, ctx.path["solution_id"], lock=True)
        c.run("UPDATE solutions SET visibility = 'archived' WHERE id = $1", s["id"])
        ctx.audit(c, "solution.archived", "solution", s["id"])
    return {"id": s["id"], "visibility": "archived"}


@route("DELETE", "/v1/solutions/{solution_id}", kinds=AUTHOR_KINDS, min_role="admin", status=204, tags=T, summary="Exclui rascunho (publicadas devem ser arquivadas)")
def delete(ctx: Ctx):
    with ctx.tx() as c:
        s = _owned(c, ctx, ctx.path["solution_id"], lock=True)
        if s["visibility"] != "draft":
            raise ApiError(409, "not_draft", "Somente rascunhos podem ser excluídos; arquive a solução publicada.")
        c.run("DELETE FROM solutions WHERE id = $1", s["id"])
        ctx.audit(c, "solution.deleted", "solution", s["id"])
    return None


@route("POST", "/v1/solutions/{solution_id}/confirm-review", kinds=AUTHOR_KINDS, min_role="member", tags=T,
       summary="Confirma a revisão humana de um rascunho gerado (exigida antes de publicar)")
def confirm_review(ctx: Ctx):
    with ctx.tx() as c:
        s = _owned(c, ctx, ctx.path["solution_id"], lock=True)
        if not s["generated_draft"]:
            raise ApiError(409, "not_generated", "Esta solução não é um rascunho gerado")
        left = [f for f in ("title", "summary", "problem", "approach", "objectives") if "[COMPLETAR]" in (s[f] or "")]
        if left:
            raise ApiError(422, "placeholders_left", "Há trechos [COMPLETAR] a preencher antes de confirmar a revisão", {"fields": left})
        c.run("UPDATE solutions SET human_reviewed_at = now() WHERE id = $1", s["id"])
        ctx.audit(c, "solution.human_reviewed", "solution", s["id"])
    return {"id": s["id"], "human_reviewed": True}


@route("POST", "/v1/solutions/{solution_id}/request-review", kinds=AUTHOR_KINDS, min_role="admin", tags=T, summary="Pede verificação à administração")
def request_review(ctx: Ctx):
    with ctx.tx() as c:
        s = _owned(c, ctx, ctx.path["solution_id"])
        if s["visibility"] != "published":
            raise ApiError(409, "not_published", "Publique a solução antes de pedir verificação")
        c.run("UPDATE solutions SET review_requested_at = now() WHERE id = $1", s["id"])
        ctx.audit(c, "solution.review_requested", "solution", s["id"])
    return {"requested": True}


@route("GET", "/v1/solutions/{solution_id}/versions", min_role="viewer", tags=T, summary="Histórico de versões (somente a organização autora)")
def versions(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        _owned(c, ctx, ctx.path["solution_id"])
        return {"items": c.query("SELECT version, changed_by::text AS changed_by, at, snapshot->>'title' AS title, snapshot->>'stage' AS stage, snapshot->>'trust_level' AS trust_level"
                                 " FROM solution_versions WHERE solution_id = $1 ORDER BY version DESC", ctx.path["solution_id"])}


# ------------------------------------------------------------------------------------------------ componentes do cadastro
@route("PUT", "/v1/solutions/{solution_id}/people", body=S.SolutionPeopleIn, kinds=AUTHOR_KINDS, min_role="member", tags=T, summary="Define autoria e equipe (substitui a lista)")
def put_people(ctx: Ctx, body: S.SolutionPeopleIn):
    with ctx.tx() as c:
        s = _owned(c, ctx, ctx.path["solution_id"])
        c.run("DELETE FROM solution_people WHERE solution_id = $1", s["id"])
        for i, p in enumerate(body.people):
            c.run("INSERT INTO solution_people(solution_id, name, role, institution, position) VALUES ($1,$2,$3,$4,$5)", s["id"], p.name, p.role, p.institution, i)
        ctx.audit(c, "solution.people_set", "solution", s["id"], {"count": len(body.people)})
    return {"count": len(body.people)}


@route("POST", "/v1/solutions/{solution_id}/evidence", body=S.SolutionEvidenceIn, kinds=AUTHOR_KINDS, min_role="member", status=201, tags=T,
       summary="Anexa evidência (nasce 'enviada'; só a administração aceita)")
def add_evidence(ctx: Ctx, body: S.SolutionEvidenceIn):
    with ctx.tx() as c:
        s = _owned(c, ctx, ctx.path["solution_id"])
        if body.document_id and not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2", body.document_id, ctx.org_id):
            raise not_found("Documento")
        if not body.url and not body.document_id:
            raise ApiError(422, "evidence_needs_source", "Informe a URL (https) ou um documento já enviado à plataforma")
        eid = c.scalar("INSERT INTO solution_evidence(solution_id, org_id, kind, title, description, url, document_id, source_type, source_date)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id::text", s["id"], ctx.org_id, body.kind, body.title, body.description, body.url,
                       body.document_id, body.source_type, body.source_date)
        ctx.audit(c, "solution.evidence_added", "solution", s["id"], {"evidence_id": eid, "kind": body.kind})
    return {"id": eid, "status": "submitted"}


@route("POST", "/v1/solutions/{solution_id}/results", body=S.SolutionResultIn, kinds=AUTHOR_KINDS, min_role="member", status=201, tags=T,
       summary="Registra resultado/indicador (nasce 'reportado'; só a administração valida)")
def add_result(ctx: Ctx, body: S.SolutionResultIn):
    with ctx.tx() as c:
        s = _owned(c, ctx, ctx.path["solution_id"])
        if s["kind"] == "idea":
            raise ApiError(422, "idea_no_results", "Ideias não têm resultados executados; registre resultados apenas em projetos/metodologias executados.")
        if body.evidence_id and not c.one("SELECT 1 FROM solution_evidence WHERE id = $1 AND solution_id = $2", body.evidence_id, s["id"]):
            raise not_found("Evidência")
        rid = c.scalar("INSERT INTO solution_results(solution_id, indicator, unit, baseline, value, period, evidence_id) VALUES ($1,$2,$3,$4::numeric,$5::numeric,$6,$7) RETURNING id::text",
                       s["id"], body.indicator, body.unit, body.baseline, body.value, body.period, body.evidence_id)
        ctx.audit(c, "solution.result_added", "solution", s["id"], {"result_id": rid})
    return {"id": rid, "status": "reported"}


@route("PUT", "/v1/solutions/{solution_id}/replication-profile", body=S.SolutionReplProfileIn, kinds=AUTHOR_KINDS, min_role="member", tags=T,
       summary="Perfil de replicação declarado pelo autor (base do score de replicabilidade)")
def put_repl_profile(ctx: Ctx, body: S.SolutionReplProfileIn):
    d = body.model_dump()
    with ctx.tx() as c:
        s = _owned(c, ctx, ctx.path["solution_id"])
        cols = list(d)
        c.run("INSERT INTO solution_replication_profile(solution_id, " + ", ".join(cols) + ") VALUES ($1, " + ", ".join(
            f"${i + 2}" + ("::text[]" if isinstance(d[k], list) else "") for i, k in enumerate(cols)) + ") ON CONFLICT (solution_id) DO UPDATE SET " +
            ", ".join(f"{k} = EXCLUDED.{k}" for k in cols) + ", updated_at = now()", s["id"], *[d[k] for k in cols])
        ctx.audit(c, "solution.replication_profile_set", "solution", s["id"])
    return {"saved": True}


@route("POST", "/v1/solutions/{solution_id}/relationships", body=S.SolutionRelationIn, kinds=AUTHOR_KINDS, min_role="member", status=201, tags=T,
       summary="Relaciona esta solução a outra (derivada de, replica, complementa, combinada com)")
def add_relation(ctx: Ctx, body: S.SolutionRelationIn):
    with ctx.tx() as c:
        s = _owned(c, ctx, ctx.path["solution_id"])
        if body.to_id == s["id"]:
            raise ApiError(422, "self_relation", "Uma solução não pode se relacionar com ela mesma")
        if not c.one("SELECT 1 FROM solutions WHERE id = $1 AND visibility = 'published'", body.to_id):
            raise not_found("Solução relacionada")
        c.run("INSERT INTO solution_relationships(from_id, to_id, rel_type, created_by_org, note) VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
              s["id"], body.to_id, body.rel_type, ctx.org_id, body.note)
    return {"saved": True}


# ------------------------------------------------------------------------------------------------ perfil
def _profile(c, ctx: Ctx, s: dict, *, own: bool) -> dict:
    sid = s["id"]
    f = svc.features(c, [sid])[sid]
    sc = svc.scores_for(s, f)
    author = c.one("SELECT legal_name, trade_name, kind, city, uf, compliance_status FROM organizations WHERE id = $1", s["org_id"])
    people = c.query("SELECT name, role, institution FROM solution_people WHERE solution_id = $1 ORDER BY position", sid)
    ev_filter = "" if own else " AND status <> 'rejected'"
    evidence = c.query("SELECT id::text AS id, kind, title, description, url, source_type, source_date, status, reviewed_at FROM solution_evidence"
                       " WHERE solution_id = $1" + ev_filter + " ORDER BY created_at", sid)
    for e in evidence:
        e["status_label"] = {"submitted": "ENVIADA — AGUARDA REVISÃO", "accepted": "ACEITA PELA REVISÃO", "rejected": "REJEITADA"}[e["status"]]
    results = c.query("SELECT id::text AS id, indicator, unit, baseline::float AS baseline, value::float AS value, period, evidence_id::text AS evidence_id, status FROM solution_results"
                      " WHERE solution_id = $1 ORDER BY created_at", sid)
    for r in results:
        r["status_label"] = "VALIDADO" if r["status"] == "validated" else "REPORTADO PELO AUTOR (não validado)"
    rels = c.query("SELECT r.rel_type, r.note, o.id::text AS id, o.title FROM solution_relationships r JOIN solutions o ON o.id = r.to_id AND o.visibility = 'published'"
                   " WHERE r.from_id = $1 UNION ALL SELECT r.rel_type || '_by', r.note, o.id::text, o.title FROM solution_relationships r JOIN solutions o ON o.id = r.from_id AND o.visibility = 'published'"
                   " WHERE r.to_id = $1", sid)
    reviews = c.query("SELECT rating, body, created_at FROM solution_reviews WHERE solution_id = $1 ORDER BY created_at DESC LIMIT 20", sid)
    stats = c.scalar("SELECT solution_public_stats($1)", sid)
    full = {k: s[k] for k in ("problem", "approach", "objectives", "learnings", "challenges", "limitations", "usage_conditions", "ip_notes", "goals", "schedule", "beneficiaries_count",
                              "team_size", "period_start", "period_end", "project_id", "parent_id")}
    access = {"level": "full"}
    if not own and s["confidentiality"] == "shareable_on_request":
        granted = c.one("SELECT 1 FROM solution_requests WHERE solution_id = $1 AND requester_org_id = $2 AND status = 'accepted'", sid, ctx.org_id)
        if not granted:
            # Compartilhável mediante autorização: só o resumo é público até o autor aceitar um pedido de informações.
            for k in ("problem", "approach", "objectives", "learnings", "challenges", "limitations", "usage_conditions", "ip_notes"):
                full[k] = None
            full["goals"], full["schedule"] = [], []
            evidence, results = [], []
            access = {"level": "summary_only", "message": "Conteúdo completo disponível mediante autorização do autor. Envie um pedido de informações."}
    card = svc.public_card(s, sc, mine=True)   # perfil: visibilidade sempre informada (a RLS só entrega publicadas ou da própria org)
    pro = inst_svc.proponents(c, [s["org_id"]]).get(s["org_id"])
    card["proponent"] = pro
    card["funding_readiness"] = readiness.compute(s, f, pro)
    mine_state = {"saved": bool(c.one("SELECT 1 FROM solution_saves WHERE user_id = $1 AND solution_id = $2", ctx.user_id, sid)),
                  "intent": c.one("SELECT id::text AS id, stage, public_identity, confirmed_by_author FROM solution_intents WHERE solution_id = $1 AND org_id = $2", sid, ctx.org_id),
                  "requests": c.query("SELECT id::text AS id, kind, status, created_at FROM solution_requests WHERE solution_id = $1 AND requester_org_id = $2 ORDER BY created_at DESC", sid, ctx.org_id)}
    return {**card, **full, "author": {**author, "name": author["trade_name"] or author["legal_name"]}, "people": people, "evidence": evidence, "results": results,
            "replication_profile": f["replication_profile"], "scores_detail": {"maturity": sc["maturity"], "evidence": sc["evidence"], "replicability": sc["replicability"]},
            "relationships": rels, "reviews": {"items": reviews, "average": round(sum(r["rating"] for r in reviews) / len(reviews), 2) if reviews else None,
                                                "note": "Avaliações vêm de quem teve relação real com a solução e NÃO entram no ranking."},
            "provenance": {"trust_level": s["trust_level"], "trust_label": SC.TRUST_LABEL[s["trust_level"]], "source_type": s["source_type"], "source_name": s["source_name"],
                           "source_date": s["source_date"], "verified_at": s["verified_at"], "verification_note": s["verification_note"], "disputed": s["disputed"],
                           "current_version": s["current_version"], "updated_at": s["updated_at"]},
            "stats": stats, "mine": mine_state, "is_owner": own, "access": access}


@route("GET", "/v1/solutions/{solution_id}", min_role="viewer", tags=T, summary="Perfil completo da solução com proveniência, evidências e pontuações explicadas")
def get_one(ctx: Ctx):
    sid = ctx.path["solution_id"]
    with ctx.tx(readonly=True) as c:
        s = _readable(c, sid)
        own = s["org_id"] == ctx.org_id
        out = _profile(c, ctx, s, own=own)
    if not own:
        with ctx.tx() as c:  # visualização: no máximo 1 evento por usuário/dia, nunca cria intenção
            c.run("INSERT INTO solution_events(solution_id, org_id, user_id, event_type) VALUES ($1,$2,$3,'solution_viewed')"
                  " ON CONFLICT (solution_id, user_id, event_type, day) WHERE solution_id IS NOT NULL DO NOTHING", sid, ctx.org_id, ctx.user_id)
    return out


@route("GET", "/v1/solutions/{solution_id}/funnel", min_role="viewer", tags=T, summary="Funil de interesse (organizações distintas; somente o autor)")
def funnel(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        _owned(c, ctx, ctx.path["solution_id"])
        f = c.scalar("SELECT solution_funnel($1)", ctx.path["solution_id"])
        stats = c.scalar("SELECT solution_public_stats($1)", ctx.path["solution_id"])
    return {"funnel": f, "stats": stats, "note": "Contagens de organizações distintas, com deduplicação diária; visualizações não são intenção."}


# ------------------------------------------------------------------------------------------------ busca
@route("POST", "/v1/solutions/search", body=S.SolutionSearchIn, min_role="viewer", rate=("solution_search", 120, 600), tags=T,
       summary="Busca híbrida por intenção: texto livre + filtros; resposta explica por que cada resultado apareceu")
def search(ctx: Ctx, body: S.SolutionSearchIn):
    q = body.model_dump()
    if (q.get("budget_min_cents") is not None and q.get("budget_max_cents") is not None and q["budget_min_cents"] > q["budget_max_cents"]):
        raise ApiError(422, "budget_range", "O valor mínimo não pode ser maior que o máximo")
    with ctx.tx() as c:
        out = svc.search(c, q, user_id=ctx.user_id, org_id=ctx.org_id)
        intent = I.parse(q.get("text") or "")
        svc.log_search(c, ctx.user_id, ctx.org_id, q.get("text") or "", intent, body.view, len(out["items"]))
    out["view"] = body.view
    return out


@route("POST", "/v1/solutions/intent/parse", body=S.SolutionTextIn, min_role="viewer", rate=("solution_search", 120, 600), tags=T,
       summary="Mostra como o texto livre é interpretado (conceitos, ODS, território, orçamento) — sem executar a busca")
def intent_parse(ctx: Ctx, body: S.SolutionTextIn):
    ii = inst_intent.parse(body.text)
    out = I.parse(ii["remaining"] if ii["matched"] else body.text)
    out["institutional"] = {k: ii[k] for k in ("qualifications", "legal_natures", "modalities", "funding_ready", "matched")}
    return out


@route("GET", "/v1/solutions/vocabulary", min_role="viewer", tags=T, summary="Vocabulário controlado (temas, populações, instituições) para filtros e cadastro")
def vocabulary(ctx: Ctx):
    cfg = K.load()["concepts"]
    return {"themes": sorted(catalog.CAUSES), "theme_labels": dict(catalog._TAX["causes"]), "population": [{"id": k, "label": v["label"]} for k, v in cfg.items() if v["dim"] == "population"],
            "institutions": [{"id": k, "label": v["label"]} for k, v in cfg.items() if v["dim"] == "institution"],
            "stages": {k: v for k, v in SC.STAGE_LABEL.items()}, "kinds": SC.KIND_LABEL, "trust_levels": SC.TRUST_LABEL}


@route("GET", "/v1/solutions/aggregates", min_role="viewer", tags=T, summary="Contagens por UF, ODS e tipo das soluções publicadas (mapa e visão por ODS)")
def aggregates(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return c.scalar("SELECT solution_aggregates()")


@route("GET", "/v1/solutions/{solution_id}/similar", min_role="viewer", tags=T, summary="“Quero algo como este”: soluções parecidas, com filtro opcional pelo meu território")
def similar(ctx: Ctx):
    sid = ctx.path["solution_id"]
    with ctx.tx(readonly=True) as c:
        base = _readable(c, sid)
        rows = c.query(f"SELECT {svc.CARD_COLS}, similarity(s.title_norm, $2) AS sim FROM solutions s WHERE s.visibility = 'published' AND s.id <> $1"
                       " AND (s.themes && $3::text[] OR s.population && $4::text[] OR s.ods && $5::smallint[] OR s.institutions && $6::text[]) LIMIT 200",
                       sid, K.norm(base["title"]), base["themes"], base["population"], base["ods"], base["institutions"])
        feats = svc.features(c, [r["id"] for r in rows])
        mine_uf = c.scalar("SELECT uf FROM organizations WHERE id = $1", ctx.org_id)

    def jac(a, b):
        a, b = set(a or []), set(b or [])
        return len(a & b) / len(a | b) if a | b else None

    items = []
    for r in rows:
        parts = [(0.35, jac(base["themes"], r["themes"])), (0.25, jac(base["population"], r["population"])), (0.2, jac(base["ods"], r["ods"])),
                 (0.1, jac(base["institutions"], r["institutions"])), (0.1, r["sim"])]
        parts = [(w, v) for w, v in parts if v is not None]
        sc = round(100 * sum(w * v for w, v in parts) / sum(w for w, _ in parts), 1) if parts else None
        why = [n for n, v in (("Temas em comum", jac(base["themes"], r["themes"])), ("Mesma população", jac(base["population"], r["population"])),
                              ("ODS em comum", jac(base["ods"], r["ods"]))) if v]
        card = svc.public_card(r, svc.scores_for(r, feats[r["id"]]))
        items.append({**card, "similarity": sc, "why": why, "same_territory_as_me": bool(mine_uf and r["uf"] == mine_uf),
                      "same_territory_as_original": bool(base["uf"] and r["uf"] == base["uf"])})
    items = [i for i in items if i["similarity"] and i["similarity"] >= 15]
    items.sort(key=lambda x: -x["similarity"])
    return {"base": {"id": sid, "title": base["title"]}, "items": items[:12], "my_uf": mine_uf, "basis": "temas, população, ODS, instituições e título (determinístico)"}


@route("POST", "/v1/solutions/compare", body=S.SolutionIdsIn, min_role="viewer", tags=T, summary="Compara 2 a 4 soluções lado a lado")
def compare(ctx: Ctx, body: S.SolutionIdsIn):
    ids = list(dict.fromkeys(body.ids))
    if len(ids) < 2:
        raise ApiError(422, "compare_needs_two", "Informe ao menos 2 soluções diferentes")
    with ctx.tx() as c:
        rows = [svc.get_solution(c, i) for i in ids]
        if any(r is None for r in rows):
            raise not_found("Solução")
        feats = svc.features(c, ids)
        cols = []
        for r in rows:
            sc = svc.scores_for(r, feats[r["id"]])
            cols.append({**svc.public_card(r, sc), "problem": r["problem"], "approach": r["approach"], "learnings": r["learnings"], "limitations": r["limitations"],
                         "beneficiaries_count": r["beneficiaries_count"], "replication_profile": feats[r["id"]]["replication_profile"]})
        for r in rows:
            if r["org_id"] != ctx.org_id:
                c.run("INSERT INTO solution_events(solution_id, org_id, user_id, event_type) VALUES ($1,$2,$3,'solution_compared') ON CONFLICT (solution_id, user_id, event_type, day) WHERE solution_id IS NOT NULL DO NOTHING",
                      r["id"], ctx.org_id, ctx.user_id)
    def best(key, fn, lo=True):
        vals = [(fn(x), x["id"]) for x in cols if fn(x) is not None]
        return (min(vals) if lo else max(vals))[1] if vals else None
    return {"columns": cols, "highlights": {"lowest_budget": best("b", lambda x: x["budget_cents"]), "highest_evidence": best("e", lambda x: x["scores"]["evidence"], lo=False),
                                           "highest_replicability": best("r", lambda x: x["scores"]["replicability"], lo=False),
                                           "highest_maturity": best("m", lambda x: x["scores"]["maturity"], lo=False)},
            "note": "“Mais evidência” refere-se às evidências cadastradas e revisadas, não à qualidade ou eficácia da solução."}


@route("POST", "/v1/solutions/combine", body=S.SolutionCombineIn, kinds=AUTHOR_KINDS, min_role="member", status=201, tags=T,
       summary="Combina 2 a 4 soluções: complementaridade, sobreposição, conflitos, dependências — sugestão que exige revisão humana")
def combine(ctx: Ctx, body: S.SolutionCombineIn):
    ids = list(dict.fromkeys(body.ids))
    if len(ids) < 2:
        raise ApiError(422, "combine_needs_two", "Informe ao menos 2 soluções diferentes")
    with ctx.tx() as c:
        rows = [svc.get_solution(c, i) for i in ids]
        if any(r is None for r in rows):
            raise not_found("Solução")
        res = combine_engine.combine(rows)
        cid = c.scalar("INSERT INTO solution_combinations(org_id, user_id, title, solution_ids, analysis, engine_version) VALUES ($1,$2,$3,$4::uuid[],$5::jsonb,$6) RETURNING id::text",
                       ctx.org_id, ctx.user_id, body.title, ids, Json(res), combine_engine.ENGINE_VERSION)
    return {"id": cid, **res}


@route("GET", "/v1/solutions/combinations", min_role="viewer", query=S.Pagination, tags=T, summary="Combinações geradas pela minha organização")
def list_combinations(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, title, solution_ids::text[] AS solution_ids, status, created_at, analysis FROM solution_combinations WHERE org_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                       ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/solutions/{solution_id}/adapt", body=S.SolutionAdaptIn, min_role="member", tags=T,
       summary="ADAPTAÇÃO SUGERIDA — NECESSITA VALIDAÇÃO: o que mudar para outro território/orçamento (ou 'dados insuficientes')")
def adapt(ctx: Ctx, body: S.SolutionAdaptIn):
    sid = ctx.path["solution_id"]
    with ctx.tx() as c:
        s = _readable(c, sid)
        if s["visibility"] != "published" and s["org_id"] != ctx.org_id:
            raise not_found("Solução")
        if s["confidentiality"] == "restricted_use" and s["org_id"] != ctx.org_id:
            raise ApiError(403, "restricted_use", "Uso restrito: o autor permite consulta, mas não adaptação por terceiros.")
        rp = svc.features(c, [sid])[sid]["replication_profile"]
        inputs = body.model_dump(exclude_none=True)
        res = adapt_engine.adapt(s, rp, inputs)
        aid = None
        if res["status"] != "blocked":
            aid = c.scalar("INSERT INTO solution_adaptations(solution_id, org_id, user_id, inputs, result, engine_version) VALUES ($1,$2,$3,$4::jsonb,$5::jsonb,$6) RETURNING id::text",
                           sid, ctx.org_id, ctx.user_id, Json(inputs), Json(res), adapt_engine.ENGINE_VERSION)
    if res["status"] == "blocked":
        raise ApiError(403, "adaptation_not_allowed", res["reason"], {"required_action": res["required_action"]})
    return {"id": aid, **res}


@route("GET", "/v1/solutions/{solution_id}/adaptations", min_role="viewer", tags=T, summary="Adaptações que a minha organização já simulou para esta solução")
def list_adaptations(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT id::text AS id, inputs, result, status, created_at FROM solution_adaptations WHERE solution_id = $1 AND org_id = $2 ORDER BY created_at DESC LIMIT 20",
                                 ctx.path["solution_id"], ctx.org_id)}


@route("POST", "/v1/solutions/{solution_id}/develop", kinds=AUTHOR_KINDS, min_role="member", status=201, tags=T,
       summary="“Desenvolver esta ideia”: cria um RASCUNHO derivado (gerado por regras, com [COMPLETAR]); exige revisão humana para publicar")
def develop(ctx: Ctx):
    sid = ctx.path["solution_id"]
    with ctx.tx() as c:
        s = _readable(c, sid)
        if s["org_id"] != ctx.org_id and s["confidentiality"] == "restricted_use":
            raise ApiError(403, "restricted_use", "Uso restrito: o autor permite consulta, mas não desenvolvimento derivado por terceiros.")
        if s["org_id"] != ctx.org_id and (s["visibility"] != "published" or not s["allow_adaptation"]):
            raise ApiError(403, "adaptation_not_allowed", "O autor não autorizou o desenvolvimento/adaptação desta solução.")
        credit = f"Baseado em “{s['title']}” (v{s['current_version']})."
        new = c.scalar(
            "INSERT INTO solutions(org_id, created_by, parent_id, kind, stage, title, summary, problem, approach, objectives, themes, population, institutions, ods, esg, license,"
            " attribution_required, generated_draft, source_type, source_name) VALUES ($1,$2,$3,'project','proposal',$4,$5,$6,$7,$8,$9::text[],$10::text[],$11::text[],$12::smallint[],$13::text[],"
            "'all_rights_reserved',true,true,'author',$14) RETURNING id::text",
            ctx.org_id, ctx.user_id, sid, ("[COMPLETAR] Desenvolvimento: " + s["title"])[:200], f"[COMPLETAR] Proposta derivada da solução “{s['title']}”. {credit}"[:1500],
            "[COMPLETAR] Descreva o problema no seu território, com dados locais.", "[COMPLETAR] Descreva como a abordagem original será adaptada. Ponto de partida do autor: " + (s["approach"] or s["summary"])[:1500],
            "[COMPLETAR] Objetivos e metas para o seu contexto.", s["themes"], s["population"], s["institutions"], s["ods"], s["esg"], f"Derivado de: {s['title']}")
        c.run("INSERT INTO solution_relationships(from_id, to_id, rel_type, created_by_org) VALUES ($1,$2,'derived_from',$3)", new, sid, ctx.org_id)
        ctx.audit(c, "solution.developed_from", "solution", new, {"source": sid})
    return {"id": new, "status": "RASCUNHO GERADO — REVISÃO HUMANA OBRIGATÓRIA", "engine": "rules@1.0 (sem IA externa)",
            "next": ["Preencher os trechos [COMPLETAR]", "Confirmar a revisão humana", "Publicar"], "attribution": credit}


# ------------------------------------------------------------------------------------------------ match e recomendações
def _funder_profile(c, org_id: str) -> dict | None:
    return c.one("SELECT causes, ods, esg_focus, territories, excluded_causes, excluded_territories, ticket_min_cents, ticket_max_cents FROM funder_profiles WHERE org_id = $1", org_id)


def _prefs(c, org_id: str) -> dict:
    return c.one("SELECT populations, kinds, prefer_proven, risk_tolerance, horizon_months FROM funder_solution_prefs WHERE org_id = $1", org_id) or {}


@route("PUT", "/v1/solutions/funder-preferences", body=S.FunderSolutionPrefsIn, kinds=("company", "government", "individual"), min_role="admin", tags=T,
       summary="Tese do financiador para soluções (populações, tipos, horizonte, preferência por comprovadas, tolerância a risco)")
def put_funder_prefs(ctx: Ctx, body: S.FunderSolutionPrefsIn):
    _validate_vocab({"population": body.populations})
    with ctx.tx() as c:
        c.run("INSERT INTO funder_solution_prefs(org_id, populations, kinds, horizon_months, prefer_proven, risk_tolerance) VALUES ($1,$2::text[],$3::text[],$4,$5,$6)"
              " ON CONFLICT (org_id) DO UPDATE SET populations = EXCLUDED.populations, kinds = EXCLUDED.kinds, horizon_months = EXCLUDED.horizon_months,"
              " prefer_proven = EXCLUDED.prefer_proven, risk_tolerance = EXCLUDED.risk_tolerance, updated_at = now()",
              ctx.org_id, body.populations, body.kinds, body.horizon_months, body.prefer_proven, body.risk_tolerance)
        ctx.audit(c, "solution.funder_prefs_set", "organization", ctx.org_id)
    return {"saved": True}


@route("GET", "/v1/solutions/funder-preferences", min_role="viewer", tags=T, summary="Minha tese para soluções")
def get_funder_prefs(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"preferences": _prefs(c, ctx.org_id) or None, "profile": _funder_profile(c, ctx.org_id)}


def _match_for(c, ctx: Ctx, s: dict, f: dict, prof: dict, prefs: dict) -> dict:
    sc = svc.scores_for(s, f)
    mi = solution_match.SolutionMatchInput.build(prof, {**s, "maturity": sc["maturity"]["score"]}, prefs)
    return solution_match.evaluate(mi)


@route("POST", "/v1/solutions/{solution_id}/match", min_role="viewer", tags=T,
       summary="Aderência desta solução à tese do meu perfil de financiador (independente do plano; explicável)")
def match(ctx: Ctx):
    sid = ctx.path["solution_id"]
    with ctx.tx(readonly=True) as c:
        s = _readable(c, sid)
        prof = _funder_profile(c, ctx.org_id)
        if not prof or not (prof["causes"] or prof["ods"] or prof["territories"]):
            raise ApiError(409, "funder_profile_missing", "Cadastre o perfil de financiador (causas, ODS, territórios e faixa de investimento) para calcular a aderência.")
        res = _match_for(c, ctx, s, svc.features(c, [sid])[sid], prof, _prefs(c, ctx.org_id))
    return res


@route("GET", "/v1/solutions/recommendations", min_role="viewer", tags=T,
       summary="Recomendações com explicação: tese do financiador e, se o usuário aceitou, histórico próprio (salvas e buscas)")
def recommendations(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        prof = _funder_profile(c, ctx.org_id)
        optin = bool(c.scalar("SELECT personalization_opt_in FROM solution_preferences WHERE user_id = $1", ctx.user_id))
        out, basis = [], []
        if prof and (prof["causes"] or prof["ods"]):
            prefs = _prefs(c, ctx.org_id)
            rows = c.query(f"SELECT {svc.CARD_COLS} FROM solutions s WHERE s.visibility = 'published' AND s.org_id <> $1"
                           " AND (s.themes && $2::text[] OR s.ods && $3::smallint[]) ORDER BY s.published_at DESC LIMIT 150", ctx.org_id, prof["causes"], prof["ods"])
            feats = svc.features(c, [r["id"] for r in rows])
            for r in rows:
                m = _match_for(c, ctx, r, feats[r["id"]], prof, prefs)
                if m["eligibility"] == "blocked" or m["score"] is None:
                    continue
                out.append({**svc.public_card(r, svc.scores_for(r, feats[r["id"]])), "score": m["score"], "confidence": m["confidence"], "why": [w["detail"] for w in m["why_match"]],
                            "risks": [x["label"] for x in m["risks"]], "basis": "tese do financiador"})
            basis.append("tese do perfil de financiador")
        elif optin:
            themes = {t for r in c.query("SELECT s.themes FROM solution_saves v JOIN solutions s ON s.id = v.solution_id WHERE v.user_id = $1 AND s.visibility = 'published'", ctx.user_id) for t in r["themes"]}
            for r in c.query("SELECT intent FROM solution_search_log WHERE user_id = $1 ORDER BY at DESC LIMIT 20", ctx.user_id):
                for cid in r["intent"].get("concepts", []):
                    themes |= set(K.load()["concepts"].get(cid, {}).get("themes", []))
            if themes:
                rows = c.query(f"SELECT {svc.CARD_COLS} FROM solutions s WHERE s.visibility = 'published' AND s.org_id <> $1 AND s.themes && $2::text[] ORDER BY s.published_at DESC LIMIT 60",
                               ctx.org_id, sorted(themes))
                feats = svc.features(c, [r["id"] for r in rows])
                for r in rows:
                    common = sorted(set(r["themes"]) & themes)
                    out.append({**svc.public_card(r, svc.scores_for(r, feats[r["id"]])), "score": round(100 * len(common) / len(themes | set(r["themes"])), 1),
                                "why": ["Temas dos seus salvos/buscas: " + ", ".join(common)], "basis": "seu histórico (personalização ativada por você)"})
                basis.append("seu histórico — personalização aceita")
        out.sort(key=lambda x: -x["score"])
    msg = None
    if not out:
        msg = ("Cadastre o perfil de financiador ou ative a personalização (opcional) para receber recomendações explicadas." if not (prof and (prof["causes"] or prof["ods"])) and not optin
               else "Ainda não há soluções publicadas compatíveis.")
    return {"items": out[:20], "basis": basis, "personalization_opt_in": optin, "message": msg,
            "note": "Recomendação é sinal de apoio; o plano contratado não altera a ordem."}


@route("PUT", "/v1/solutions/personalization", body=S.SolutionPrefsIn, min_role="viewer", tags=T, summary="Aceita ou recusa personalização por histórico (padrão: recusada)")
def put_personalization(ctx: Ctx, body: S.SolutionPrefsIn):
    with ctx.tx() as c:
        c.run("INSERT INTO solution_preferences(user_id, personalization_opt_in) VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET personalization_opt_in = EXCLUDED.personalization_opt_in, updated_at = now()",
              ctx.user_id, body.personalization_opt_in)
        if not body.personalization_opt_in:
            c.run("DELETE FROM solution_search_log WHERE user_id = $1", ctx.user_id)
    return {"personalization_opt_in": body.personalization_opt_in, "history_deleted": not body.personalization_opt_in}


@route("POST", "/v1/solutions/assistant", body=S.SolutionTextIn, min_role="viewer", rate=("solution_search", 120, 600), tags=T,
       summary="Copiloto ancorado nos dados: responde SOMENTE com soluções realmente cadastradas (sem texto gerado por modelo)")
def assistant(ctx: Ctx, body: S.SolutionTextIn):
    with ctx.tx() as c:
        res = svc.search(c, {"text": body.text, "limit": 5, "offset": 0}, include_trace=False)
        intent = I.parse(body.text)
        svc.log_search(c, ctx.user_id, ctx.org_id, body.text, intent, "assistant", len(res["items"]))
    items = res["items"]
    if not items:
        msg = "Não encontrei soluções cadastradas para este pedido."
    else:
        msg = f"Encontrei {len(items)} solução(ões) cadastrada(s) na biblioteca que combinam com o seu pedido. As informações são as declaradas pelos autores, com o nível de verificação indicado em cada uma."
    return {"message": msg, "interpretation": res["intent"], "suggestions": [{"id": i["id"], "title": i["title"], "label": i["labels"]["primary"], "trust": i["labels"]["trust"],
                                                                         "why": i["relevance"]["why"]} for i in items], "next_steps": res.get("empty", {}).get("suggestions", [
        "Abra o perfil para ver evidências e proveniência", "Use “Adaptar para meu território” ou “Quero algo como este”"]),
            "grounded": True, "ai_used": False, "disclaimer": "Resposta construída apenas a partir de registros da biblioteca; não é recomendação de investimento."}
