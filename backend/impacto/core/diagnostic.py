"""Motor de diagnóstico: versão imutável, comparação entre versões e plano de ação a partir das lacunas.

Não é um assistente que conversa. É um motor que olha o que a plataforma **sabe de fato** sobre a organização, o projeto
e o território, e devolve estado atual, forças, lacunas, riscos, evidências ausentes, ações recomendadas e confiança.

Três regras que não se negociam:
1. **Sem evidência é `UNKNOWN`**, nunca um palpite. Nada é preenchido por IA.
2. **Fato, inferência e recomendação são campos separados** — quem lê sabe o que é dado e o que é opinião da máquina.
3. **Versão nova nunca apaga a anterior.** `diagnoses` é o diagnóstico corrente e editável; cada publicação congela uma
   versão imutável em `diagnosis_versions`, e a comparação entre versões é o que mostra evolução.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from ..db.pq import Connection, Json
from ..services.audit import ledger
from .evidence import Evidence, EvidenceSet, Source, band

ENGINE_VERSION = "diagnostic-engine@1.0.0"

# Dimensões do diagnóstico. Cada uma tem peso na completude e sabe dizer o que falta.
DIMENSIONS: tuple[tuple[str, str, int], ...] = (
    ("identity", "Identidade institucional", 10),
    ("compliance", "Documentação e regularidade", 15),
    ("governance", "Governança e equipe", 10),
    ("problem", "Problema e evidências", 15),
    ("territory", "Território e público", 10),
    ("solution", "Solução e atividades", 10),
    ("budget", "Orçamento e sustentabilidade", 15),
    ("measurement", "Metas e indicadores", 15),
)
GAP_SEVERITY = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _collect(conn: Connection, *, org_id: str, project_id: str | None, diagnosis: dict | None) -> EvidenceSet:
    """Lê o que a plataforma SABE. Nada aqui é inferido — cada evidência diz de onde veio."""
    ev = EvidenceSet()
    org = conn.one("SELECT id::text AS id, legal_name, cnpj, founded_on, legal_nature, city, uf, team_size,"
                   " compliance_status, description, causes, ods, updated_at FROM organizations WHERE id = $1", org_id)
    if org:
        ev.add(Evidence("org.legal_name", Source.DECLARED, org["legal_name"], observed_at=org["updated_at"], kind="profile"))
        ev.add(Evidence("org.cnpj", Source.PLATFORM_RECORD if org["cnpj"] else Source.ABSENT, org["cnpj"],
                        observed_at=org["updated_at"], kind="profile", detail="CNPJ validado no cadastro"))
        ev.add(Evidence("org.legal_nature", Source.DECLARED, org["legal_nature"], observed_at=org["updated_at"], kind="profile"))
        ev.add(Evidence("org.team_size", Source.DECLARED, org["team_size"], observed_at=org["updated_at"], kind="profile"))
        ev.add(Evidence("org.territory", Source.DECLARED, f"{org['city']}/{org['uf']}" if org["city"] else None,
                        observed_at=org["updated_at"], kind="profile"))
        ev.add(Evidence("org.compliance", Source.PLATFORM_RECORD if org["compliance_status"] == "approved" else Source.ABSENT,
                        org["compliance_status"] if org["compliance_status"] == "approved" else None,
                        observed_at=org["updated_at"], kind="compliance",
                        detail="cadastro institucional aprovado pela plataforma"))
        ev.add(Evidence("org.description", Source.DECLARED, org["description"], observed_at=org["updated_at"], kind="profile"))
    # documentos vigentes do cofre: evidência VERIFICADA (passaram pelo cofre e estão na validade)
    for d in conn.query("SELECT doc_type, max(valid_until) AS valid_until, max(created_at) AS created_at, count(*) AS n"
                        " FROM documents WHERE org_id = $1 AND deleted_at IS NULL AND status IN ('clean','pending_scan')"
                        " GROUP BY doc_type", org_id):
        ev.add(Evidence(f"doc.{d['doc_type']}", Source.VERIFIED_DOCUMENT, d["n"], observed_at=d["created_at"],
                        expires_at=d["valid_until"], kind="document", detail=f"{d['n']} documento(s) no cofre"))
    # qualificações e credenciais: só contam como verificadas quando a equipe conferiu
    for q in conn.query("SELECT qualification_type, verification_status, expiration_date, updated_at"
                        " FROM organization_qualifications WHERE org_id = $1", org_id):
        src = Source.VERIFIED_CREDENTIAL if q["verification_status"] == "verified" else Source.DECLARED
        ev.add(Evidence(f"qualification.{q['qualification_type']}", src, q["verification_status"],
                        observed_at=q["updated_at"], expires_at=q["expiration_date"], kind="credential"))
    for c in conn.query("SELECT council, verification_status, valid_until, created_at FROM professional_credentials"
                        " WHERE org_id = $1", org_id):
        src = Source.VERIFIED_CREDENTIAL if c["verification_status"] == "verified" else Source.DECLARED
        ev.add(Evidence(f"credential.{c['council']}", src, c["verification_status"], observed_at=c["created_at"],
                        expires_at=c["valid_until"], kind="credential"))
    if project_id:
        p = conn.one("SELECT title, problem, objectives, methodology, territory, budget_total_cents, starts_on, ends_on,"
                     " beneficiaries_count, beneficiaries_description, status, updated_at, ods"
                     " FROM projects WHERE id = $1", project_id)
        if p:
            for key, kind in (("problem", "project_activity"), ("objectives", "project_activity"),
                              ("methodology", "project_activity"), ("territory", "profile"),
                              ("beneficiaries_description", "profile")):
                ev.add(Evidence(f"project.{key}", Source.DECLARED, p[key], observed_at=p["updated_at"], kind=kind))
            # 0 não é "informado": orçamento zerado e público zerado são ausência de dado, não declaração
            ev.add(Evidence("project.budget", Source.DECLARED, p["budget_total_cents"] or None,
                            observed_at=p["updated_at"], kind="budget"))
            ev.add(Evidence("project.schedule", Source.DECLARED,
                            f"{p['starts_on']}–{p['ends_on']}" if p["starts_on"] and p["ends_on"] else None,
                            observed_at=p["updated_at"], kind="budget"))
            ev.add(Evidence("project.beneficiaries", Source.DECLARED, p["beneficiaries_count"] or None,
                            observed_at=p["updated_at"], kind="profile"))
            ev.add(Evidence("project.ods", Source.DECLARED, list(p["ods"] or []) or None, observed_at=p["updated_at"], kind="profile"))
        n_ms = conn.scalar("SELECT count(*) FROM milestones WHERE project_id = $1", project_id)
        ev.add(Evidence("project.milestones", Source.PLATFORM_RECORD if n_ms else Source.ABSENT, n_ms or None,
                        observed_at=datetime.now(UTC), kind="project_activity"))
        n_ind = conn.scalar("SELECT count(*) FROM project_indicators WHERE project_id = $1", project_id)
        ev.add(Evidence("project.indicators", Source.PLATFORM_RECORD if n_ind else Source.ABSENT, n_ind or None,
                        observed_at=datetime.now(UTC), kind="indicator"))
        meas = conn.one("SELECT count(*) AS n, max(measured_on) AS last FROM indicator_values iv"
                        " WHERE iv.project_id = $1 AND iv.status = 'validated'", project_id)
        ev.add(Evidence("project.validated_measurements",
                        Source.VALIDATED_MEASUREMENT if (meas and meas["n"]) else Source.ABSENT,
                        (meas or {}).get("n") or None, observed_at=(meas or {}).get("last"), kind="indicator"))
        n_sig = conn.scalar("SELECT count(*) FROM signatures s JOIN documents d ON d.id = s.subject_id"
                            " WHERE d.project_id = $1", project_id)
        ev.add(Evidence("project.signed_documents", Source.SIGNED_DOCUMENT if n_sig else Source.ABSENT, n_sig or None,
                        observed_at=datetime.now(UTC), kind="document"))
    if diagnosis:
        for key in ("need_statement", "affected_group", "objective"):
            ev.add(Evidence(f"diagnosis.{key}", Source.DECLARED, diagnosis.get(key),
                            observed_at=diagnosis.get("updated_at"), kind="diagnosis"))
        for key in ("root_causes", "goals", "action_plan", "risks", "data_sources"):
            val = diagnosis.get(key) or []
            ev.add(Evidence(f"diagnosis.{key}", Source.DECLARED if val else Source.ABSENT, len(val) or None,
                            observed_at=diagnosis.get("updated_at"), kind="diagnosis"))
    return ev


# Lacuna: (código, dimensão, título, severidade, evidência que fecha, chaves exigidas)
GAPS: tuple[tuple[str, str, str, str, str, tuple[str, ...]], ...] = (
    ("missing_cnpj", "identity", "Organização sem CNPJ registrado", "high",
     "Comprovante de inscrição no CNPJ", ("org.cnpj",)),
    ("missing_legal_nature", "identity", "Natureza jurídica não informada", "medium", "Estatuto social", ("org.legal_nature",)),
    ("compliance_not_approved", "compliance", "Cadastro institucional ainda não aprovado", "critical",
     "Documentos do cadastro enviados para análise", ("org.compliance",)),
    ("missing_statute", "compliance", "Estatuto social ausente no cofre", "high", "Estatuto social registrado", ("doc.estatuto_social",)),
    ("missing_board", "compliance", "Ata de eleição da diretoria ausente", "high", "Ata registrada", ("doc.ata_eleicao_diretoria",)),
    ("no_team_size", "governance", "Tamanho da equipe não informado", "low", "Quadro de pessoal", ("org.team_size",)),
    ("no_problem", "problem", "Problema não descrito", "critical", "Descrição do problema com fonte", ("project.problem", "diagnosis.need_statement")),
    ("no_evidence_sources", "problem", "Nenhuma fonte de dados citada para o problema", "high",
     "Dado, relatório ou registro que sustenta o problema", ("diagnosis.data_sources",)),
    ("no_root_causes", "problem", "Causas do problema não identificadas", "medium", "Análise de causas", ("diagnosis.root_causes",)),
    ("no_territory", "territory", "Território de atuação não informado", "high", "Município/bairro de atuação", ("project.territory", "org.territory")),
    ("no_audience", "territory", "Público afetado não descrito", "high", "Descrição agregada do público", ("project.beneficiaries_description", "diagnosis.affected_group")),
    ("no_audience_size", "territory", "Quantidade de pessoas atendidas não estimada", "medium", "Estimativa de alcance", ("project.beneficiaries",)),
    ("no_methodology", "solution", "Atividades e metodologia não descritas", "high", "Plano de atividades", ("project.methodology",)),
    ("no_objective", "solution", "Objetivo não definido", "critical", "Objetivo com prazo e público", ("project.objectives", "diagnosis.objective")),
    ("no_budget", "budget", "Orçamento não informado", "critical", "Planilha orçamentária", ("project.budget",)),
    ("no_schedule", "budget", "Cronograma não definido", "high", "Datas de início e fim", ("project.schedule",)),
    ("no_milestones", "budget", "Nenhum marco definido", "medium", "Marcos com prazo e valor", ("project.milestones",)),
    ("no_goals", "measurement", "Metas não definidas", "critical", "Metas com indicador e prazo", ("diagnosis.goals", "project.indicators")),
    ("no_indicators", "measurement", "Nenhum indicador de resultado", "high", "Indicadores do catálogo", ("project.indicators",)),
    ("no_measurements", "measurement", "Nenhuma medição validada", "medium", "Medição com evidência, validada por terceiro", ("project.validated_measurements",)),
)
# Força: o inverso da lacuna. Só é força quando a evidência está presente E é verificada.
STRENGTH_KEYS: tuple[tuple[str, str, str], ...] = (
    ("org.compliance", "compliance", "Cadastro institucional aprovado pela plataforma"),
    ("doc.estatuto_social", "compliance", "Estatuto social no cofre"),
    ("project.validated_measurements", "measurement", "Medições validadas por outra organização"),
    ("project.signed_documents", "solution", "Documentos do projeto assinados"),
)


def analyse(conn: Connection, *, org_id: str, project_id: str | None = None, diagnosis: dict | None = None) -> dict:
    """Produz o diagnóstico. Saída separa FATO (evidence), INFERÊNCIA (gaps/risks) e RECOMENDAÇÃO (actions)."""
    ev = _collect(conn, org_id=org_id, project_id=project_id, diagnosis=diagnosis)
    gaps, unknown = [], []
    for code, dim, title, severity, hint, keys in GAPS:
        present = [k for k in keys if ev.get(k).present]
        if present:
            continue
        if all(ev.get(k).source is Source.ABSENT and ev.get(k).value is None for k in keys) and not any(k in ev.items for k in keys):
            unknown.append({"code": code, "dimension": dim, "title": title,
                            "detail": "não há dado na plataforma para avaliar este ponto"})
        gaps.append({"code": code, "dimension": dim, "title": title, "severity": severity,
                     "evidence_hint": hint, "keys": list(keys)})
    strengths = [{"key": k, "dimension": d, "title": t, "evidence": ev.get(k).as_dict()}
                 for k, d, t in STRENGTH_KEYS if ev.get(k).present]
    stale = ev.stale()
    # completude por dimensão: proporção das lacunas daquela dimensão que estão fechadas
    per_dim, total_w, got_w = [], 0, 0.0
    for dim, label, weight in DIMENSIONS:
        dim_gaps = [g for g in gaps if g["dimension"] == dim]
        dim_total = len([g for g in GAPS if g[1] == dim]) or 1
        closed = dim_total - len(dim_gaps)
        pct = round(100 * closed / dim_total, 1)
        per_dim.append({"dimension": dim, "label": label, "weight": weight, "closed": closed,
                        "total": dim_total, "percent": pct, "gaps": [g["code"] for g in dim_gaps]})
        total_w += weight
        got_w += weight * closed / dim_total
    completeness = round(100 * got_w / total_w, 1) if total_w else 0.0
    summary = ev.summary()
    confidence = summary["mean_confidence"]
    conf_band = band(confidence, summary["known"], summary["total"])
    actions = [{"gap_code": g["code"], "title": f"Resolver: {g['title']}", "detail": g["evidence_hint"],
                "evidence_hint": g["evidence_hint"],
                "priority": {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}[g["severity"]],
                "origin": "system_identified"}
               for g in sorted(gaps, key=lambda g: -GAP_SEVERITY[g["severity"]])]
    return {
        "engine_version": ENGINE_VERSION,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "scope": {"org_id": org_id, "project_id": project_id},
        # FATO
        "evidence": ev.as_dict(),
        "evidence_summary": summary,
        # INFERÊNCIA (da plataforma, por regra — não é verdade absoluta)
        "current_state": {"completeness": completeness, "by_dimension": per_dim,
                          "blocking_gaps": [g["code"] for g in gaps if g["severity"] == "critical"]},
        "strengths": strengths,
        "gaps": gaps,
        "unknown": unknown,
        "stale_evidence": stale,
        "missing_evidence": [{"key": k, "why": "exigido por pelo menos uma lacuna"} for k in ev.missing()],
        # RECOMENDAÇÃO
        "recommended_actions": actions[:20],
        "confidence": confidence,
        "confidence_band": conf_band.value,
        "priority": "high" if [g for g in gaps if g["severity"] == "critical"] else ("medium" if gaps else "low"),
        "disclaimer": "Diagnóstico de apoio: lacunas e riscos são apontados por REGRA a partir do que a plataforma "
                      "conhece. Ausência de dado aparece como desconhecido, nunca como suposição. A decisão é humana.",
    }


# ------------------------------------------------------------------------------------------------ versões
# Campos que mudam a cada leitura sem que NADA tenha mudado na organização. Entrar no hash faria "congelar versão"
# criar versão nova a cada segundo — e "o que mudou" passaria a ser uma pergunta sobre o relógio, não sobre o projeto.
VOLATILE = ("generated_at",)


def _digest(payload: dict) -> str:
    stable = {k: v for k, v in payload.items() if k not in VOLATILE}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _diff(prev: dict | None, cur: dict) -> dict[str, Any]:
    """O que mudou da versão anterior para esta. Calculado pelo servidor, nunca declarado pela usuária."""
    if not prev:
        return {"first_version": True, "closed_gaps": [], "new_gaps": [], "new_strengths": [],
                "completeness_delta": cur["current_state"]["completeness"],
                "confidence_delta": cur["confidence"]}
    pg = {g["code"] for g in prev.get("gaps", [])}
    cg = {g["code"] for g in cur.get("gaps", [])}
    ps = {s["key"] for s in prev.get("strengths", [])}
    cs = {s["key"] for s in cur.get("strengths", [])}
    return {
        "first_version": False,
        "closed_gaps": sorted(pg - cg),
        "new_gaps": sorted(cg - pg),
        "new_strengths": sorted(cs - ps),
        "lost_strengths": sorted(ps - cs),
        "completeness_delta": round(cur["current_state"]["completeness"] - prev["current_state"]["completeness"], 1),
        "confidence_delta": round(cur["confidence"] - prev["confidence"], 1),
    }


def publish_version(conn: Connection, *, diagnosis_id: str, org_id: str, created_by: str | None) -> dict:
    """Congela uma versão imutável do diagnóstico. A versão anterior NUNCA é alterada."""
    from ..http import ApiError
    d = conn.one("SELECT id::text AS id, org_id::text AS org_id, project_id::text AS project_id, title,"
                 " need_statement, affected_group, root_causes, objective, goals, action_plan, risks, data_sources,"
                 " updated_at FROM diagnoses WHERE id = $1", diagnosis_id)
    if not d:
        raise ApiError(404, "not_found", "Diagnóstico não encontrado")
    payload = analyse(conn, org_id=org_id, project_id=d["project_id"], diagnosis=d)
    prev = conn.one("SELECT version, payload FROM diagnosis_versions WHERE diagnosis_id = $1 ORDER BY version DESC LIMIT 1",
                    diagnosis_id)
    digest = _digest(payload)
    if prev and _digest(prev["payload"]) == digest:
        return {"created": False, "version": prev["version"], "reason": "nada mudou desde a versão anterior"}
    version = (prev["version"] + 1) if prev else 1
    changes = _diff(prev["payload"] if prev else None, payload)
    row = conn.one("INSERT INTO diagnosis_versions(diagnosis_id, org_id, version, payload, payload_sha256, changes,"
                   " completeness, confidence, engine_version, created_by)"
                   " VALUES ($1,$2,$3,$4::jsonb,$5,$6::jsonb,$7,$8,$9,$10) RETURNING id::text AS id, created_at",
                   diagnosis_id, org_id, version, Json(payload), digest, Json(changes),
                   payload["current_state"]["completeness"], payload["confidence"], ENGINE_VERSION, created_by)
    # ações: cria o que falta, fecha o que a lacuna deixou de existir. Ação já tratada pela pessoa não é mexida.
    created, closed = [], []
    for a in payload["recommended_actions"]:
        exists = conn.one("SELECT id::text AS id, status FROM diagnosis_actions WHERE diagnosis_id = $1 AND gap_code = $2",
                          diagnosis_id, a["gap_code"])
        if exists is None:
            aid = conn.scalar("INSERT INTO diagnosis_actions(diagnosis_id, org_id, project_id, gap_code, title, detail,"
                              " evidence_hint, priority, origin) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'system_identified')"
                              " RETURNING id::text", diagnosis_id, org_id, d["project_id"], a["gap_code"], a["title"],
                              a["detail"], a["evidence_hint"], a["priority"])
            created.append(aid)
    open_codes = {a["gap_code"] for a in payload["recommended_actions"]}
    for row2 in conn.query("SELECT id::text AS id, gap_code FROM diagnosis_actions WHERE diagnosis_id = $1"
                           " AND status IN ('open','in_progress') AND origin = 'system_identified'", diagnosis_id):
        if row2["gap_code"] and row2["gap_code"] not in open_codes:
            conn.run("UPDATE diagnosis_actions SET status = 'done', done_at = now() WHERE id = $1", row2["id"])
            closed.append(row2["id"])
    if d["project_id"]:
        ledger(conn, project_id=d["project_id"], org_id=org_id, actor=created_by,
               entry_type="diagnosis_revised" if prev else "diagnosis_created", ref_type="diagnosis",
               ref_id=diagnosis_id, payload={"version": version, "completeness": payload["current_state"]["completeness"],
                                             "closed_gaps": changes.get("closed_gaps", [])})
    # Valor registrado só quando a versão REALMENTE nasce: a saída antecipada acima ("nada mudou") não
    # passa por aqui, e com isso congelar duas vezes não conta duas vezes.
    from ..economics import value_ledger
    value_ledger.record(conn, event_type="diagnosis.version_published", org_id=org_id, units=1,
                        project_id=d["project_id"], subject_type="diagnosis", subject_id=diagnosis_id,
                        engine_version=ENGINE_VERSION,
                        metrics={"version": version, "actions_created": len(created),
                                 "actions_auto_closed": len(closed),
                                 "completeness": payload["current_state"]["completeness"]})
    return {"created": True, "id": row["id"], "version": version, "created_at": row["created_at"],
            "completeness": payload["current_state"]["completeness"], "confidence": payload["confidence"],
            "changes": changes, "actions_created": len(created), "actions_auto_closed": len(closed)}


def versions(conn: Connection, diagnosis_id: str) -> list[dict]:
    return conn.query("SELECT id::text AS id, version, completeness, confidence, changes, engine_version, created_at,"
                      " created_by::text AS created_by, user_display_name(created_by) AS created_by_name,"
                      " payload_sha256 FROM diagnosis_versions WHERE diagnosis_id = $1 ORDER BY version DESC",
                      diagnosis_id)


def compare_versions(conn: Connection, diagnosis_id: str, a: int, b: int) -> dict:
    rows = {r["version"]: r for r in conn.query(
        "SELECT version, payload, completeness, confidence, created_at FROM diagnosis_versions"
        " WHERE diagnosis_id = $1 AND version = ANY($2::int[])", diagnosis_id, [a, b])}
    if a not in rows or b not in rows:
        return {"found": False}
    pa, pb = rows[a]["payload"], rows[b]["payload"]
    return {"found": True, "from": {"version": a, "at": rows[a]["created_at"], "completeness": rows[a]["completeness"],
                                    "confidence": rows[a]["confidence"]},
            "to": {"version": b, "at": rows[b]["created_at"], "completeness": rows[b]["completeness"],
                   "confidence": rows[b]["confidence"]},
            "what_changed": _diff(pa, pb)}
