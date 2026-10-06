"""Recomendação ≠ match. São duas perguntas diferentes e o pedido insiste nessa separação (§42).

    MATCH          — "quem combina comigo?"              → compatibilidade entre duas entidades, com peso e versão
    RECOMENDAÇÃO   — "o que eu deveria fazer agora?"     → próxima ação, com a razão e a evidência que a sustenta

Confundir as duas produz o pior dos dois mundos: um feed de oportunidades que ninguém sabe por que apareceu, e uma
lista de tarefas que não sabe o que está acontecendo na rede. Então: o motor de match (`match-engine@1.2.0`) continua
intocado e responde compatibilidade; este motor LÊ o diagnóstico, as prontidões, as propostas e o match, e devolve
AÇÃO.

Três regras que este módulo não negocia:
  1. **Toda recomendação diz por quê** (`rationale`) e de onde veio (`evidence`, `match_run_id`,
     `diagnosis_version_id`). Recomendação sem razão é palpite com cara de algoritmo.
  2. **A confiança é herdada, não inventada.** Quando a base é fraca, a faixa é `insufficient_data` e isso aparece —
     em vez de um número bonito sobre nada.
  3. **Nunca recomenda com base em relação privada.** A recomendação lê a própria organização e dados públicos; não
     usa "quem mais favoritou este projeto", porque favorito é privado (ver `relationships.MAX_VISIBILITY`).
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, Json
from ..http import forbidden, not_found
from . import marketplace, readiness

ENGINE_VERSION = "recommendation@1.0.0"

ACTIONS = ("complete_diagnosis", "complete_project", "add_indicator", "add_milestone", "upload_document",
           "publish_project", "create_listing", "send_proposal", "review_proposal", "find_professional",
           "find_investor", "apply_to_call", "submit_impact_update", "resolve_risk", "renew_document",
           "confirm_experience", "measure_indicator", "review_match", "invite_member")

#: Para onde cada ação leva. Recomendação que não abre a tela da ação é recado, não recomendação.
#:
#: TODO DESTINO AQUI É UMA ROTA REAL DO APLICATIVO, e há um teste de arquitetura que confere isso
#: (`test_recommendation_links_exist_in_the_app`). Ele foi escrito porque sete destes links estavam errados na
#: primeira versão — eu os escrevi pelo nome que me pareceu natural (`/projetos/{id}/indicadores`,
#: `/rede/profissionais`, `/match`) em vez de pelo nome que o aplicativo usa. Cada um apareceria no workspace e o
#: clique cairia em "página não encontrada", que é pior do que não recomendar nada.
LINKS: dict[str, str] = {
    "complete_diagnosis": "/diagnosticos", "complete_project": "/projetos/{id}",
    "add_indicator": "/projetos/{id}/impacto", "add_milestone": "/projetos/{id}",
    "upload_document": "/documentos", "publish_project": "/projetos/{id}",
    "create_listing": "/marketplace/meus", "send_proposal": "/propostas/nova",
    "review_proposal": "/propostas/{id}", "find_professional": "/profissionais",
    "find_investor": "/marketplace", "apply_to_call": "/oportunidades",
    "submit_impact_update": "/projetos/{id}/relatorios", "resolve_risk": "/projetos/{id}/riscos",
    "renew_document": "/documentos", "confirm_experience": "/rede/experiencias",
    "measure_indicator": "/projetos/{id}/impacto", "review_match": "/projetos/{id}/impacto",
    "invite_member": "/organizacao",
}


def _band(confidence: float | None, known: int, total: int) -> str:
    """Faixa de confiança. `insufficient_data` quando a base é rala — a mesma regra do motor de evidência (0013)."""
    if total == 0 or known / max(total, 1) < 0.4:
        return "insufficient_data"
    if confidence is None:
        return "insufficient_data"
    if confidence >= 75:
        return "high"
    if confidence >= 45:
        return "medium"
    return "low"


class _Rec:
    __slots__ = ("action", "subject_type", "subject_id", "title", "rationale", "priority", "confidence",
                 "band", "evidence")

    def __init__(self, action: str, subject_type: str, subject_id: str | None, title: str, rationale: str,
                 priority: int, confidence: float | None, band: str, evidence: dict):
        self.action, self.subject_type, self.subject_id = action, subject_type, subject_id
        self.title, self.rationale, self.priority = title, rationale, priority
        self.confidence, self.band, self.evidence = confidence, band, evidence


def compute(conn: Connection, *, org_id: str, user_id: str | None = None, limit: int = 20) -> list[dict]:
    """Calcula as próximas ações da organização. Não grava — `refresh()` é quem persiste."""
    recs: list[_Rec] = []
    projects = conn.query(
        "SELECT p.id::text AS id, p.title, p.status, p.visibility,"
        " (SELECT count(*) FROM project_indicators i WHERE i.project_id = p.id) AS indicators,"
        " (SELECT count(*) FROM milestones m WHERE m.project_id = p.id) AS milestones,"
        " (SELECT count(*) FROM project_risks r WHERE r.project_id = p.id"
        "    AND r.status IN ('open','materialized') AND r.severity IN ('high','critical')) AS hot_risks,"
        # a versão do diagnóstico pendura no DIAGNÓSTICO, que pendura no projeto — dois saltos, não um
        " (SELECT max(dv.version) FROM diagnosis_versions dv JOIN diagnoses d ON d.id = dv.diagnosis_id"
        "    WHERE d.project_id = p.id) AS diag_version"
        " FROM projects p WHERE p.org_id = $1 AND p.status NOT IN ('archived','cancelled','rejected')"
        " ORDER BY p.updated_at DESC LIMIT 40", org_id)

    for p in projects:
        r = readiness.evaluate(conn, org_id=org_id, project_id=p["id"])
        known = sum(1 for d in r["dimensions"].values() if d.get("checks"))
        conf = r["overall"]
        bnd = _band(conf, known, len(readiness.DIMENSIONS))
        ev_base = {"readiness_overall": r["overall"], "engine": readiness.ENGINE_VERSION,
                   "dimensions": {k: v["score"] for k, v in r["dimensions"].items()}}

        if not p["diag_version"]:
            recs.append(_Rec("complete_diagnosis", "project", p["id"],
                             f"Fazer o diagnóstico de “{p['title']}”",
                             "O projeto ainda não tem diagnóstico. Sem ele, a plataforma não consegue dizer o que "
                             "falta nem sugerir quem pode ajudar.", 95, conf, bnd, ev_base))
        if r["scores"]["project_readiness"] < 70:
            miss = [b["blocker"] for b in r["blockers"] if b["dimension"] == "project_readiness"][:3]
            recs.append(_Rec("complete_project", "project", p["id"],
                             f"Completar a descrição de “{p['title']}”",
                             f"Prontidão de projeto em {r['scores']['project_readiness']}%. Pendências: "
                             + "; ".join(miss) + ".", 85, r["scores"]["project_readiness"], bnd,
                             {**ev_base, "blockers": miss}))
        if int(p["indicators"] or 0) == 0:
            recs.append(_Rec("add_indicator", "project", p["id"],
                             f"Definir indicadores em “{p['title']}”",
                             "Sem indicador não há como comprovar resultado depois — e é o que financiador pede "
                             "primeiro.", 88, conf, bnd, ev_base))
        elif r["scores"]["evidence_readiness"] < 60:
            recs.append(_Rec("measure_indicator", "project", p["id"],
                             f"Lançar medições em “{p['title']}”",
                             f"Prontidão de evidência em {r['scores']['evidence_readiness']}%: há indicador definido, "
                             "mas falta medição ou validação.", 70, r["scores"]["evidence_readiness"], bnd, ev_base))
        if int(p["milestones"] or 0) == 0:
            recs.append(_Rec("add_milestone", "project", p["id"],
                             f"Definir marcos em “{p['title']}”",
                             "Marcos com prazo e valor permitem desembolso por etapa e acompanhamento real.",
                             75, conf, bnd, ev_base))
        if r["scores"]["document_readiness"] < 80:
            miss = [b["blocker"] for b in r["blockers"] if b["dimension"] == "document_readiness"][:3]
            recs.append(_Rec("upload_document", "organization", None,
                             "Completar a documentação institucional",
                             f"Prontidão documental em {r['scores']['document_readiness']}%. "
                             + "; ".join(miss) + ".", 90, r["scores"]["document_readiness"], bnd,
                             {**ev_base, "blockers": miss}))
        if p["visibility"] != "published" and r["scores"]["project_readiness"] >= 70:
            recs.append(_Rec("publish_project", "project", p["id"],
                             f"Publicar “{p['title']}”",
                             f"A descrição já está em {r['scores']['project_readiness']}% e o projeto continua "
                             "privado — publicar é o que o torna visível a quem pode apoiar.", 80, conf, bnd,
                             ev_base))
        # A pergunta "tem anúncio no ar?" é do marketplace, e é ele quem a responde — ver
        # marketplace.has_published_listing e o invariante que impede a condição de se espalhar.
        has_listing = marketplace.has_published_listing(conn, p["id"])
        if p["visibility"] == "published" and not has_listing and r["scores"]["funding_readiness"] >= 60:
            recs.append(_Rec("create_listing", "project", p["id"],
                             f"Criar anúncio para “{p['title']}”",
                             f"O projeto está publicado e com prontidão de captação em "
                             f"{r['scores']['funding_readiness']}%, mas não está no marketplace.", 72, conf, bnd,
                             ev_base))
        if int(p["hot_risks"] or 0):
            recs.append(_Rec("resolve_risk", "project", p["id"],
                             f"Tratar {p['hot_risks']} risco(s) de severidade alta em “{p['title']}”",
                             "Risco aberto de severidade alta bloqueia avanço de etapa e aparece a quem avalia o "
                             "projeto.", 92, conf, bnd, {**ev_base, "hot_risks": int(p["hot_risks"])}))

    if not projects:
        # ACHADO (jornada 1): uma organização recém-criada não tinha NENHUMA recomendação, porque todas dependiam
        # de existir projeto. O workspace abria vazio justamente para quem mais precisa de direção. Estas duas são
        # o primeiro passo real de quem acabou de entrar.
        r = readiness.evaluate(conn, org_id=org_id)
        recs.append(_Rec("complete_project", "organization", None, "Criar o primeiro projeto",
                         "A plataforma organiza o trabalho em torno de projetos: é o projeto que recebe "
                         "diagnóstico, documentos, apoio e prestação de contas.", 90, None, "insufficient_data",
                         {"reason": "sem projeto"}))
        if r["scores"]["document_readiness"] < 100:
            miss = [b["blocker"] for b in r["blockers"] if b["dimension"] == "document_readiness"][:3]
            recs.append(_Rec("upload_document", "organization", None,
                             "Completar a documentação institucional",
                             f"Prontidão documental em {r['scores']['document_readiness']}%. "
                             + "; ".join(miss) + ".", 94, r["scores"]["document_readiness"],
                             "high", {"blockers": miss}))
        if r["scores"]["governance_readiness"] < 70:
            recs.append(_Rec("invite_member", "organization", None,
                             "Definir responsáveis na organização",
                             f"Prontidão de governança em {r['scores']['governance_readiness']}%: depender de uma "
                             "pessoa só é o risco mais comum em organização pequena.", 70,
                             r["scores"]["governance_readiness"], "medium", {}))

    recs += _proposal_recs(conn, org_id)
    recs += _document_recs(conn, org_id)
    recs += _match_recs(conn, org_id)
    recs += _report_recs(conn, org_id)

    recs.sort(key=lambda r: (-r.priority, r.title))
    out = []
    for r in recs[:limit]:
        link = LINKS[r.action]
        out.append({"action": r.action, "subject_type": r.subject_type, "subject_id": r.subject_id,
                    "title": r.title, "rationale": r.rationale, "priority": r.priority,
                    "confidence": r.confidence, "confidence_band": r.band, "evidence": r.evidence,
                    "link": link.replace("{id}", r.subject_id) if r.subject_id and "{id}" in link
                            else link.replace("/{id}", ""),
                    "engine_version": ENGINE_VERSION})
    return out


def _proposal_recs(conn: Connection, org_id: str) -> list[_Rec]:
    """Proposta esperando resposta é a ação mais urgente que existe: do outro lado há alguém parado."""
    rows = conn.query(
        "SELECT p.id::text AS id, p.title, p.status, p.sent_at,"
        " coalesce(o.trade_name, o.legal_name) AS sender,"
        " extract(day from now() - p.sent_at)::int AS days"
        " FROM proposals p JOIN organizations o ON o.id = p.sender_org_id"
        " WHERE p.receiver_org_id = $1 AND p.status IN ('sent','viewed','in_review')"
        " ORDER BY p.sent_at LIMIT 10", org_id)
    out = []
    for r in rows:
        days = int(r["days"] or 0)
        out.append(_Rec("review_proposal", "proposal", r["id"], f"Responder à proposta de {r['sender']}",
                        f"“{r['title']}” está aguardando há {days} dia(s). Quem enviou está esperando decisão.",
                        min(100, 90 + min(days, 10)), None, "insufficient_data",
                        {"days_waiting": days, "status": r["status"]}))
    rows = conn.query(
        "SELECT id::text AS id, title FROM proposals WHERE sender_org_id = $1 AND status = 'changes_requested'"
        " ORDER BY updated_at LIMIT 5", org_id)
    for r in rows:
        out.append(_Rec("send_proposal", "proposal", r["id"], f"Revisar e reenviar “{r['title']}”",
                        "A outra parte pediu ajuste. Reenviar gera uma nova versão, preservando a anterior.",
                        86, None, "insufficient_data", {"reason": "changes_requested"}))
    return out


def _document_recs(conn: Connection, org_id: str) -> list[_Rec]:
    """Documento a vencer é a recomendação mais fácil de acertar e a mais cara de perder."""
    rows = conn.query(
        "SELECT id::text AS id, title, doc_type, valid_until,"
        " (valid_until - current_date) AS days FROM documents"
        " WHERE org_id = $1 AND deleted_at IS NULL AND valid_until IS NOT NULL"
        "   AND valid_until <= current_date + 60 ORDER BY valid_until LIMIT 10", org_id)
    out = []
    for r in rows:
        d = int(r["days"] or 0)
        out.append(_Rec("renew_document", "document", r["id"],
                        ("Documento vencido: " if d < 0 else "Documento a vencer: ") + r["title"],
                        (f"Venceu há {abs(d)} dia(s)." if d < 0 else f"Vence em {d} dia(s).")
                        + " Documento vencido derruba a prontidão documental e trava candidatura a edital.",
                        98 if d < 0 else 80, None, "high", {"days_to_expiry": d, "doc_type": r["doc_type"]}))
    return out


def _match_recs(conn: Connection, org_id: str) -> list[_Rec]:
    """Rodadas de match com nota alta que ninguém olhou.

    `match_runs` já é UMA linha por par avaliado (com `score`, `confidence` e `evidence`) — não há tabela de
    resultados à parte. A evidência da recomendação é a própria rodada: id, versões do motor e nota.
    """
    rows = conn.query(
        "SELECT r.project_id::text AS project_id, p.title, count(*) AS strong, max(r.score) AS best,"
        " max(r.created_at) AS at,"
        # a rodada citada como evidência é a de MAIOR nota; não existe max(uuid), então vem por subconsulta
        " (SELECT b.id::text FROM match_runs b WHERE b.viewer_org_id = r.viewer_org_id"
        "    AND b.project_id = r.project_id ORDER BY b.score DESC, b.created_at DESC LIMIT 1) AS run_id,"
        " (SELECT b.engine_version FROM match_runs b WHERE b.viewer_org_id = r.viewer_org_id"
        "    AND b.project_id = r.project_id ORDER BY b.score DESC, b.created_at DESC LIMIT 1)"
        "   AS engine_version"
        " FROM match_runs r JOIN projects p ON p.id = r.project_id"
        " WHERE r.viewer_org_id = $1 AND r.score >= 70 AND r.eligibility = 'eligible'"
        "   AND r.outcome IS NULL AND r.created_at > now() - interval '30 days'"
        " GROUP BY r.viewer_org_id, r.project_id, p.title"
        " ORDER BY max(r.created_at) DESC LIMIT 5", org_id)
    return [_Rec("review_match", "project", r["project_id"],
                 f"{r['strong']} oportunidade(s) com boa compatibilidade para “{r['title']}”",
                 f"A análise de {r['at']:%d/%m} encontrou {r['strong']} resultado(s) com nota {int(r['best'])} ou "
                 f"menos, nenhum ainda avaliado por você. Compatibilidade não é garantia — é ponto de partida.",
                 76, float(r["best"]), "medium",
                 {"match_run_id": r["run_id"], "engine_version": r["engine_version"],
                  "strong": int(r["strong"]), "best_score": float(r["best"])})
            for r in rows]


def _report_recs(conn: Connection, org_id: str) -> list[_Rec]:
    """Projeto em execução sem relatório no período: é o que quebra a confiança de quem apoiou."""
    rows = conn.query(
        "SELECT p.id::text AS id, p.title,"
        " (SELECT max(u.period_end) FROM impact_updates u WHERE u.project_id = p.id"
        "    AND u.status IN ('accepted','published')) AS last_report"
        " FROM projects p WHERE p.org_id = $1 AND p.status IN ('in_execution','monitoring','funded')"
        " ORDER BY p.updated_at DESC LIMIT 10", org_id)
    out = []
    for r in rows:
        if r["last_report"] is None:
            why = "O projeto está em execução e ainda não teve nenhum relatório de impacto aceito."
            prio = 84
        else:
            why = f"O último relatório aceito cobre até {r['last_report']:%d/%m/%Y}."
            prio = 68
        out.append(_Rec("submit_impact_update", "project", r["id"],
                        f"Enviar relatório de impacto de “{r['title']}”", why, prio, None, "insufficient_data",
                        {"last_report": str(r["last_report"]) if r["last_report"] else None}))
    return out


# ------------------------------------------------------------------------------------------------ persistência

def refresh(conn: Connection, *, org_id: str, user_id: str | None = None, limit: int = 20) -> dict:
    """Recalcula e guarda. Recomendação que deixou de valer vira `superseded`, não desaparece.

    Apagar silenciosamente seria perder a resposta a "por que a plataforma me disse isso em março?". O índice único
    parcial garante uma recomendação ABERTA por (organização, ação, sujeito) — repetir o cálculo não duplica.
    """
    fresh = compute(conn, org_id=org_id, user_id=user_id, limit=limit)
    keys = {(r["action"], r["subject_type"], r["subject_id"]) for r in fresh}
    open_rows = conn.query(
        "SELECT id::text AS id, action, subject_type, subject_id::text AS subject_id FROM recommendations"
        " WHERE org_id = $1 AND status = 'open'", org_id)
    superseded = 0
    for o in open_rows:
        if (o["action"], o["subject_type"], o["subject_id"]) not in keys:
            conn.run("UPDATE recommendations SET status = 'superseded' WHERE id = $1", o["id"])
            superseded += 1
    created = 0
    for r in fresh:
        n = conn.run(
            "INSERT INTO recommendations(org_id, user_id, action, subject_type, subject_id, title, rationale,"
            " confidence, confidence_band, evidence, priority, engine_version)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12)"
            # o índice ux_rec_open é (org_id, action, coalesce(subject_id, zero)) WHERE status='open';
            # a cláusula ON CONFLICT tem de repetir o índice ao pé da letra, sem subject_type.
            " ON CONFLICT (org_id, action, coalesce(subject_id,"
            " '00000000-0000-0000-0000-000000000000'::uuid)) WHERE status = 'open' DO UPDATE"
            " SET title = excluded.title, rationale = excluded.rationale, confidence = excluded.confidence,"
            " confidence_band = excluded.confidence_band, evidence = excluded.evidence,"
            " priority = excluded.priority, engine_version = excluded.engine_version",
            org_id, user_id, r["action"], r["subject_type"], r["subject_id"], r["title"], r["rationale"],
            r["confidence"], r["confidence_band"], Json(r["evidence"]), r["priority"], ENGINE_VERSION)
        created += n
    return {"computed": len(fresh), "written": created, "superseded": superseded,
            "engine_version": ENGINE_VERSION}


def listing(conn: Connection, *, org_id: str, status: str = "open", limit: int = 30) -> list[dict]:
    rows = conn.query(
        "SELECT id::text AS id, action, subject_type, subject_id::text AS subject_id, title, rationale,"
        " confidence, confidence_band, evidence, priority, status, engine_version, created_at"
        " FROM recommendations WHERE org_id = $1 AND status = $2"
        " ORDER BY priority DESC, created_at DESC LIMIT $3", org_id, status, limit)
    for r in rows:
        link = LINKS.get(r["action"], "/")
        r["link"] = (link.replace("{id}", r["subject_id"]) if r["subject_id"] and "{id}" in link
                     else link.replace("/{id}", ""))
    return rows


def resolve(conn: Connection, *, rec_id: str, org_id: str, status: str, reason: str | None = None) -> dict:
    """Marca como feita ou descartada. Descartar com motivo ensina o motor a não repetir."""
    r = conn.one("SELECT org_id::text AS org_id, status FROM recommendations WHERE id = $1", rec_id)
    if not r:
        raise not_found("Recomendação")
    if r["org_id"] != org_id:
        raise forbidden("Recomendação de outra organização")
    if status not in ("done", "dismissed"):
        from ..http import unprocessable
        raise unprocessable("Situação permitida: done ou dismissed")
    conn.run("UPDATE recommendations SET status = $2, dismissed_reason = $3 WHERE id = $1", rec_id, status, reason)
    return {"id": rec_id, "status": status}


def counts(conn: Connection, org_id: str) -> dict[str, Any]:
    r = conn.one(
        "SELECT count(*) FILTER (WHERE status = 'open') AS open,"
        " count(*) FILTER (WHERE status = 'open' AND priority >= 85) AS urgent,"
        " count(*) FILTER (WHERE status = 'done') AS done FROM recommendations WHERE org_id = $1", org_id)
    return {k: int(v or 0) for k, v in (r or {}).items()}
