"""Orquestração do motor de similaridade: autorização pela camada de uso, leitura sob RLS, cache, gravação e contestação."""
from __future__ import annotations

import hashlib
import json

from ..engines.ai import usage_control as UC
from ..engines.similarity import engine as E
from ..http import ApiError, not_found, unprocessable

KIND_TO_OPERATION = {"single": "similarity.single", "pair": "similarity.pair", "set": "similarity.set",
                     "complementarity": "similarity.complementarity", "expense_overlap": "similarity.expense_overlap"}


def _visible_candidates(conn, subject: dict, limit: int = 300) -> list[dict]:
    """Projetos que o solicitante ENXERGA (a RLS decide), menos o próprio. Pré-filtro barato por causa/ODS/UF
    para não comparar o banco inteiro; o motor faz o resto."""
    rows = conn.query(
        "SELECT p.id::text AS id FROM projects p JOIN organizations o ON o.id = p.org_id"
        " WHERE p.id <> $1 AND p.status <> 'archived'"
        "   AND (p.causes && $2::text[] OR p.ods && $3::smallint[] OR o.uf = $4 OR lower(p.territory) = lower($5))"
        " ORDER BY p.updated_at DESC LIMIT $6",
        subject["id"], subject.get("causes") or [], subject.get("ods") or [], subject.get("uf"), subject.get("territory") or "", limit)
    out = []
    for r in rows:
        p = E.load_profile(conn, r["id"])
        if p:
            out.append(p)
    return out


def _inputs_hash(kind: str, subject: dict, compared: list[dict]) -> str:
    return hashlib.sha256(json.dumps({"kind": kind, "subject": E.profile_hash(subject),
                                      "compared": sorted(E.profile_hash(c) for c in compared),
                                      "engine": E.ENGINE_VERSION}, sort_keys=True).encode()).hexdigest()


def _chars(p: dict) -> int:
    return sum(len(str(p.get(k) or "")) for k in ("title", "summary", "problem", "objectives", "methodology", "beneficiaries_description"))


def analyze(ctx, *, kind: str, subject_id: str, compared_ids: list[str] | None = None, idempotency_key: str | None = None) -> dict:
    if kind not in KIND_TO_OPERATION:
        raise unprocessable(f"Tipo de análise inválido: {kind}", {"possiveis": list(KIND_TO_OPERATION)}, code="similarity_kind")
    compared_ids = list(dict.fromkeys(compared_ids or []))
    with ctx.tx() as c:
        subject = E.load_profile(c, subject_id)
        if not subject:
            raise not_found("Projeto")
        if kind in ("pair", "expense_overlap"):
            if len(compared_ids) != 1 or compared_ids[0] == subject_id:
                raise unprocessable("Esta análise compara exatamente dois projetos diferentes", code="similarity_needs_two")
        elif kind == "set":
            if not 1 <= len(compared_ids) <= 20 or subject_id in compared_ids:
                raise unprocessable("O conjunto aceita de 1 a 20 projetos, sem o próprio projeto base", code="similarity_set_size")
        if kind in ("single", "complementarity"):
            compared = _visible_candidates(c, subject)
        else:
            compared = []
            for pid in compared_ids:
                p = E.load_profile(c, pid)
                if not p:
                    # 404 genérico: não revela se o projeto existe e é de outra organização
                    raise not_found("Projeto comparado")
                compared.append(p)
        if kind == "expense_overlap" and not (subject.get("budget_items") and compared[0].get("budget_items")):
            raise unprocessable("A análise de despesas exige itens de orçamento nos dois projetos", code="similarity_no_budget")
        h = _inputs_hash(kind, subject, compared)
        cached = c.one("SELECT id::text AS id, result FROM similarity_analyses WHERE org_id = $1 AND kind = $2 AND subject_project_id = $3"
                       "   AND inputs_sha256 = $4 AND engine_version = $5 ORDER BY created_at DESC LIMIT 1",
                       ctx.org_id, kind, subject_id, h, E.ENGINE_VERSION)
        units = len(compared) if kind == "set" else 1
        input_chars = _chars(subject) + sum(_chars(p) for p in compared)
        with UC.Run(c, ctx, KIND_TO_OPERATION[kind], params={"kind": kind, "subject": subject_id, "compared": compared_ids},
                    units=units, input_chars=min(input_chars, 10**7), project_id=subject_id,
                    subject_ref=",".join(compared_ids)[:200] or None, idempotency_key=idempotency_key, cached=bool(cached)) as run:
            if cached:
                run.ok(result_type="similarity_analysis", result_id=cached["id"], meta={"provider": "local"})
                row = c.one("SELECT * FROM similarity_analyses WHERE id = $1", cached["id"])
                return _out(row, run.execution, cached=True)
            hidden = int(c.scalar("SELECT similarity_hidden_overlap($1)", subject_id) or 0) if kind in ("single", "complementarity") else 0
            if kind in ("single", "complementarity"):
                result = E.originality(subject, compared)
                if kind == "complementarity":
                    comp = [p for p in result["shown"] if p["comparison"]["readings"]["complementarity"]]
                    result = {"complementarity": comp, "candidates_compared": result["candidates_compared"],
                              "human_review_required": True,
                              "note": ("Sugestões de parceria, consórcio, divisão de território e compartilhamento de infraestrutura "
                                       "entre projetos VISÍVEIS a você com causa em comum e território ou abordagem diferentes.")}
                confidence = "medium" if compared else "low"
                if kind == "single" and result["shown"]:
                    confs = [p["comparison"]["confidence"] for p in result["shown"][:3]]
                    confidence = "high" if confs.count("high") >= 2 else ("low" if confs.count("low") >= 2 else "medium")
            elif kind == "set":
                rows = [{"project_id": p["id"], "title": p["title"], "org_name": p.get("org_name"), "comparison": E.compare(subject, p)} for p in compared]
                result = {"set": rows, "human_review_required": True}
                confidence = "medium"
            else:
                cmp_ = E.compare(subject, compared[0])
                result = {"pair": {"project_id": compared[0]["id"], "title": compared[0]["title"], "org_name": compared[0].get("org_name")}, "comparison": cmp_}
                if kind == "expense_overlap":
                    result["expense_overlap"] = {
                        "possible_duplication": cmp_["readings"]["possible_expense_duplication"],
                        "shared_items": cmp_["dimensions"]["budget"].get("shared_items", []),
                        "same_funding_source": cmp_["readings"]["same_funding_source"],
                        "temporal_overlap": cmp_["dimensions"]["time"]["score"],
                        "territorial_overlap": cmp_["dimensions"]["territory"]["score"],
                        "statement": ("INDÍCIO de possível sobreposição de despesa: itens iguais, mesmo território e períodos sobrepostos. "
                                      "Não presume irregularidade: financiamento por fontes múltiplas é legítimo quando declarado. Exige análise humana."
                                      if cmp_["readings"]["possible_expense_duplication"] else
                                      "Sem indício de sobreposição de despesa nas dimensões com dado."),
                    }
                confidence = cmp_["confidence"]
            result["engine_version"] = E.ENGINE_VERSION
            result["disclaimer"] = ("Similaridade textual ≠ similaridade de escopo ≠ sobreposição territorial ≠ duplicidade financeira "
                                    "≠ plágio ≠ fraude. Indícios por dimensão, com confiança e revisão humana; nenhuma decisão automática.")
            result["hidden_overlap_count"] = hidden
            if hidden:
                result["hidden_overlap_note"] = (f"Há {hidden} projeto(s) de outras organizações, não publicados, com a mesma causa e o mesmo "
                                                 "território — você não tem acesso a eles; só a contagem é mostrada (k-anonimato ≥ 3).")
            row = c.one("INSERT INTO similarity_analyses(org_id, execution_id, kind, subject_project_id, compared_project_ids, engine_version,"
                        " inputs_sha256, result, confidence, human_review_required, hidden_count, created_by)"
                        " VALUES ($1,$2,$3,$4,$5::uuid[],$6,$7,$8::jsonb,$9,true,$10,$11) RETURNING *",
                        ctx.org_id, run.execution["id"], kind, subject_id, [p["id"] for p in compared], E.ENGINE_VERSION, h,
                        json.dumps(result, ensure_ascii=False, default=str), confidence, hidden, ctx.user_id)
            run.ok(result_type="similarity_analysis", result_id=str(row["id"]), meta={"provider": "local"})
            ctx.audit(c, "ai.similarity_analyzed", "similarity_analysis", row["id"], {"kind": kind, "compared": len(compared), "confidence": confidence})
            return _out(row, run.execution, cached=False)


def _out(row: dict, execution: dict, *, cached: bool) -> dict:
    res = row["result"]
    if isinstance(res, str):
        res = json.loads(res)
    return {"id": str(row["id"]), "kind": row["kind"], "subject_project_id": str(row["subject_project_id"]),
            "compared_project_ids": [str(x) for x in (row["compared_project_ids"] or [])], "engine_version": row["engine_version"],
            "confidence": row["confidence"], "human_review_required": row["human_review_required"], "hidden_count": row["hidden_count"],
            "created_at": row["created_at"], "result": res, "cached": cached,
            "execution": {k: execution.get(k) for k in ("id", "state", "funding_source", "funding_label", "charged_credits", "estimated_credits", "cost_status")}}


def get(ctx, analysis_id: str) -> dict:
    with ctx.tx(readonly=True) as c:
        row = c.one("SELECT * FROM similarity_analyses WHERE id = $1 AND org_id = $2", analysis_id, ctx.org_id)
        if not row:
            raise not_found("Análise")
        ex = c.one("SELECT * FROM ai_executions WHERE id = $1", row["execution_id"]) if row["execution_id"] else None
        disputes = c.query("SELECT id::text AS id, status, reason, reviewer_note, created_at, reviewed_at FROM similarity_disputes WHERE analysis_id = $1 ORDER BY created_at", analysis_id)
    out = _out(row, UC._row(ex) if ex else {}, cached=False)
    out["disputes"] = disputes
    return out


def dispute(ctx, analysis_id: str, reason: str) -> dict:
    with ctx.tx() as c:
        row = c.one("SELECT id FROM similarity_analyses WHERE id = $1 AND org_id = $2", analysis_id, ctx.org_id)
        if not row:
            raise not_found("Análise")
        if c.one("SELECT 1 FROM similarity_disputes WHERE analysis_id = $1 AND status = 'open'", analysis_id):
            raise ApiError(409, "dispute_open", "Já existe uma contestação aberta para esta análise")
        d = c.one("INSERT INTO similarity_disputes(analysis_id, org_id, opened_by, reason) VALUES ($1,$2,$3,$4) RETURNING id::text AS id, status, created_at",
                  analysis_id, ctx.org_id, ctx.user_id, reason)
        ctx.audit(c, "ai.similarity_disputed", "similarity_analysis", analysis_id, {"dispute_id": d["id"]})
    return dict(d) | {"note": "A contestação vai para revisão humana da administração; o resultado contestado não produz efeito algum enquanto isso (nem antes produzia)."}
