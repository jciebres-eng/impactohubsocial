"""Relatório de impacto: o ciclo que fecha a cadeia e devolve resultado a quem apoiou.

O pedido descreve a cadeia inteira (§28): Pessoa/Organização → Contexto → Necessidade → Rede → Match → Proposta →
Relação → Projeto → Execução → **Evidência → Resultado** → Novo Match. Este módulo é o penúltimo elo, e o que
distingue a plataforma de um marketplace: quem apoiou recebe prestação de contas no mesmo lugar onde apoiou.

Ciclo: rascunho → enviado → em análise → (ajuste pedido ↺) → aceito → publicado.

Quatro decisões que valem registro:
  1. **A apuração é do servidor.** `metrics`, `milestones` e `evidence_count` NÃO vêm do formulário: são lidos de
     `indicator_values`, `milestones` e `evidences` no momento do envio. A organização escreve o texto; os números são
     colhidos. Sem isso, "atendemos 400 pessoas" seria digitável sem lastro.
  2. **Quem revisa não é quem escreveu** — o CHECK da tabela recusa `reviewed_by = created_by` até em SQL direto, e
     `impact_update_guard()` deriva quem revisou de `app_uid()`.
  3. **Limitações são campo do relatório.** Dizer o que o dado NÃO prova é parte de relatar com honestidade; a
     plataforma oferece o campo em vez de deixar o silêncio parecer certeza.
  4. **Publicar é decisão de quem executa, só depois de aceito.** O relatório publicado entra na projeção pública do
     perfil — e nunca antes de alguém de fora ter aceito.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, Json
from ..http import ApiError, forbidden, not_found, unprocessable
from ..services.audit import ledger
from . import notify

STATUSES = ("draft", "submitted", "under_review", "changes_requested", "accepted", "published")
OPEN = ("draft", "submitted", "under_review", "changes_requested")
ST_LABEL = {"draft": "rascunho", "submitted": "enviado", "under_review": "em análise",
            "changes_requested": "ajuste solicitado", "accepted": "aceito", "published": "publicado"}


def graph(conn: Connection) -> list[dict]:
    return conn.query("SELECT from_status, to_status, actor, requires_note, note FROM network_status_graph"
                      " WHERE entity = 'impact_update' ORDER BY from_status, to_status")


def create(conn: Connection, *, project_id: str, org_id: str, actor: str | None, period_start: Any,
           period_end: Any, summary: str, outputs: str | None = None, outcomes: str | None = None,
           limitations: str | None = None, risks_note: str | None = None) -> dict:
    """Abre o relatório em rascunho para um período. Um relatório por (projeto, período) — o UNIQUE garante."""
    p = conn.one("SELECT org_id::text AS org_id, title, status FROM projects WHERE id = $1", project_id)
    if not p:
        raise not_found("Projeto")
    if p["org_id"] != org_id:
        raise forbidden("Apenas a organização dona relata o projeto")
    exists = conn.one("SELECT id::text AS id, status FROM impact_updates WHERE project_id = $1"
                      " AND period_start = $2 AND period_end = $3", project_id, period_start, period_end)
    if exists:
        raise ApiError(409, "period_exists", "Já existe relatório para este período", exists)
    row = conn.one(
        "INSERT INTO impact_updates(project_id, org_id, period_start, period_end, summary, outputs, outcomes,"
        " limitations, risks_note, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)"
        " RETURNING id::text AS id, status, created_at",
        project_id, org_id, period_start, period_end, summary, outputs, outcomes, limitations, risks_note, actor)
    return {**row, "status_label": ST_LABEL[row["status"]], "project_title": p["title"]}


def update(conn: Connection, *, update_id: str, org_id: str, fields: dict[str, Any]) -> dict:
    """Edita o texto. Só em rascunho ou após ajuste pedido — relatório aceito não se reescreve."""
    u = _load(conn, update_id)
    if u["org_id"] != org_id:
        raise forbidden("Relatório de outra organização")
    if u["status"] not in ("draft", "changes_requested"):
        raise ApiError(409, "not_editable",
                       f"Relatório {ST_LABEL[u['status']]} não é editável; abra um relatório do período seguinte")
    allowed = {"summary", "outputs", "outcomes", "limitations", "risks_note", "document_id"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            params.append(v)
            sets.append(f"{k} = ${len(params) + 1}")
    if not sets:
        return u
    conn.run(f"UPDATE impact_updates SET {', '.join(sets)} WHERE id = $1", update_id, *params)
    return _load(conn, update_id)


def gather(conn: Connection, *, project_id: str, period_start: Any, period_end: Any) -> dict[str, Any]:
    """Apura os números do período a partir das tabelas de execução. Nada aqui vem de formulário.

    É deliberadamente uma função separada e pública: a interface pode mostrar "é isto que será apurado" ANTES do
    envio, de modo que a organização veja os números e entenda que não os digita.
    """
    indicators = conn.query(
        "SELECT ic.code, ic.name, ic.unit, pi.baseline, pi.target,"
        " (SELECT v.value FROM indicator_values v WHERE v.project_indicator_id = pi.id"
        "    AND v.measured_on BETWEEN $2 AND $3 AND v.status = 'validated'"
        "  ORDER BY v.measured_on DESC LIMIT 1) AS value_in_period,"
        " (SELECT count(*) FROM indicator_values v WHERE v.project_indicator_id = pi.id"
        "    AND v.measured_on BETWEEN $2 AND $3) AS measurements,"
        " (SELECT count(*) FROM indicator_values v WHERE v.project_indicator_id = pi.id"
        "    AND v.measured_on BETWEEN $2 AND $3 AND v.status = 'validated') AS validated"
        " FROM project_indicators pi JOIN indicator_catalog ic ON ic.id = pi.indicator_id"
        " WHERE pi.project_id = $1 ORDER BY ic.code", project_id, period_start, period_end)
    milestones = conn.query(
        "SELECT title, due_on, status, amount_cents FROM milestones"
        " WHERE project_id = $1 AND (due_on BETWEEN $2 AND $3 OR status IN ('completed','verified'))"
        " ORDER BY due_on NULLS LAST", project_id, period_start, period_end)
    evidence_count = int(conn.scalar(
        "SELECT count(*) FROM evidences WHERE project_id = $1 AND occurred_on BETWEEN $2 AND $3",
        project_id, period_start, period_end) or 0)
    validated = sum(int(i["validated"] or 0) for i in indicators)
    measured = sum(int(i["measurements"] or 0) for i in indicators)
    return {
        "indicators": indicators, "milestones": milestones, "evidence_count": evidence_count,
        "measurements": measured, "validated_measurements": validated,
        "completed_milestones": sum(1 for m in milestones if m["status"] in ("completed", "verified")),
        # A ressalva vai COM os números, não num rodapé: medição não validada não comprova resultado.
        "caveat": ("Apurado pelo servidor a partir das medições e marcos do período. "
                   + (f"{measured - validated} medição(ões) ainda não validada(s) não comprovam resultado."
                      if measured > validated else "Todas as medições do período estão validadas.")),
    }


def transition(conn: Connection, *, update_id: str, to: str, org_id: str, actor: str | None,
               note: str | None = None, admin: bool = False) -> dict:
    """Move o relatório no grafo, apurando os números no envio e validando quem pode revisar."""
    u = _load(conn, update_id)
    if to == u["status"]:
        return {**u, "unchanged": True}
    rule = conn.one("SELECT actor, requires_note FROM network_status_graph"
                    " WHERE entity = 'impact_update' AND from_status = $1 AND to_status = $2", u["status"], to)
    if not rule:
        opts = [r["to_status"] for r in conn.query(
            "SELECT to_status FROM network_status_graph WHERE entity = 'impact_update' AND from_status = $1",
            u["status"])]
        raise ApiError(409, "invalid_transition",
                       f"Relatório {ST_LABEL[u['status']]} não pode ir para {ST_LABEL.get(to, to)}",
                       {"permitidas": opts})
    is_owner = u["org_id"] == org_id
    if rule["actor"] == "owner" and not is_owner:
        raise forbidden("Apenas a organização que executa envia ou publica o relatório")
    if rule["actor"] == "reviewer":
        if is_owner:
            raise forbidden("Quem executa não revisa o próprio relatório", "self_review")
        if not admin and not _can_review(conn, u["project_id"], org_id):
            raise forbidden("Somente quem apoia o projeto (ou a administração) revisa o relatório", "not_reviewer")
    if rule["requires_note"] and not (note and len(note.strip()) >= 3):
        raise unprocessable("Pedir ajuste exige dizer o que precisa ser ajustado (mínimo 3 caracteres)")

    if to == "submitted":
        # Momento exato da apuração: o que o relatório afirma em números passa a ter origem rastreável.
        g = gather(conn, project_id=u["project_id"], period_start=u["period_start"], period_end=u["period_end"])
        conn.run("UPDATE impact_updates SET metrics = $2::jsonb, milestones = $3::jsonb, evidence_count = $4,"
                 " status = 'submitted' WHERE id = $1", update_id,
                 Json({k: v for k, v in g.items() if k != "milestones"}), Json(g["milestones"]),
                 g["evidence_count"])
    elif to == "changes_requested":
        conn.run("UPDATE impact_updates SET status = $2, review_note = $3 WHERE id = $1", update_id, to, note)
    else:
        conn.run("UPDATE impact_updates SET status = $2,"
                 " review_note = CASE WHEN $3::text IS NOT NULL THEN $3 ELSE review_note END"
                 " WHERE id = $1", update_id, to, note)

    _announce(conn, u, to=to, actor=actor, note=note)
    if to in ("accepted", "published"):
        ledger(conn, project_id=u["project_id"], org_id=u["org_id"], actor=actor,
               entry_type="impact_update_accepted" if to == "accepted" else "impact_update_published",
               ref_type="impact_update", ref_id=update_id,
               payload={"period": [str(u["period_start"]), str(u["period_end"])], "status": to})
    return {**_load(conn, update_id), "unchanged": False}


def _can_review(conn: Connection, project_id: str, org_id: str) -> bool:
    """Revisa quem apoia: financiador com candidatura aceita, ou organização com relação ativa de apoio.

    Não é "qualquer organização logada". Sem essa checagem, o aceite de um relatório de impacto não valeria nada.
    """
    if conn.one("SELECT 1 AS ok FROM applications WHERE project_id = $1 AND funder_org_id = $2"
                " AND status IN ('approved','accepted','contracted')", project_id, org_id):
        return True
    return bool(conn.one(
        "SELECT 1 AS ok FROM relationships WHERE target_project_id = $1 AND source_org_id = $2"
        " AND status = 'active' AND kind IN ('investment','sponsorship','support','government_support',"
        "'project_sponsor','project_investor','partnership','collaboration')", project_id, org_id))


def _announce(conn: Connection, u: dict, *, to: str, actor: str | None, note: str | None) -> None:
    event = {"submitted": "ImpactUpdate.submitted", "changes_requested": "ImpactUpdate.changes_requested",
             "accepted": "ImpactUpdate.accepted", "published": "ImpactUpdate.published"}.get(to)
    if not event:
        notify.fact_only(conn, event="ImpactUpdate.submitted", org_id=u["org_id"], actor_user_id=actor,
                         project_id=u["project_id"], ref_type="impact_update", ref_id=u["id"])
        return
    period = f"{u['period_start']:%d/%m/%Y} a {u['period_end']:%d/%m/%Y}"
    titles = {"submitted": "Relatório de impacto enviado", "changes_requested": "Relatório devolvido para ajuste",
              "accepted": "Relatório de impacto aceito", "published": "Relatório de impacto publicado"}
    bodies = {"submitted": f"Período {period}: o relatório de “{u['project_title']}” foi enviado para análise.",
              "changes_requested": f"Período {period}: pediram ajuste. {note or ''}".strip(),
              "accepted": f"Período {period}: o relatório foi aceito por quem apoia o projeto.",
              "published": f"Período {period}: o relatório passou a aparecer no projeto e no perfil público."}
    # A EQUIPE INTEIRA é avisada — inclusive os financiadores, que entram em project_team() pela candidatura aceita.
    notify.project_event(
        conn, event=event, project_id=u["project_id"], org_id=u["org_id"], actor_user_id=actor,
        title=titles[to], body=bodies[to], link=f"/projetos/{u['project_id']}/relatorios/{u['id']}",
        ref_type="impact_update", ref_id=u["id"],
        priority="high" if to in ("submitted", "changes_requested") else "normal",
        action_label={"submitted": "Analisar", "changes_requested": "Ajustar"}.get(to),
        dedupe_parts=(event, u["id"], to),
        payload={"period": [str(u["period_start"]), str(u["period_end"])], "status": to})


# ------------------------------------------------------------------------------------------------ leitura

_SELECT = (
    "SELECT u.id::text AS id, u.project_id::text AS project_id, u.org_id::text AS org_id, u.period_start,"
    " u.period_end, u.summary, u.outputs, u.outcomes, u.limitations, u.risks_note, u.metrics, u.milestones,"
    " u.evidence_count, u.status, u.review_note, u.reviewed_at, u.submitted_at, u.published_at, u.created_at,"
    " u.document_id::text AS document_id, u.reviewed_by_org::text AS reviewed_by_org,"
    " user_display_name(u.reviewed_by) AS reviewed_by_name, p.title AS project_title,"
    " coalesce(ro.trade_name, ro.legal_name) AS reviewed_by_org_name"
    " FROM impact_updates u JOIN projects p ON p.id = u.project_id"
    " LEFT JOIN organizations ro ON ro.id = u.reviewed_by_org")


def _load(conn: Connection, update_id: str) -> dict:
    r = conn.one(f"{_SELECT} WHERE u.id = $1", update_id)
    if not r:
        raise not_found("Relatório de impacto")
    r["status_label"] = ST_LABEL[r["status"]]
    return r


def get(conn: Connection, *, update_id: str, org_id: str, admin: bool = False) -> dict:
    u = _load(conn, update_id)
    if u["org_id"] != org_id and not admin and not _can_review(conn, u["project_id"], org_id):
        raise forbidden("Relatório visível para quem executa e para quem apoia o projeto")
    side = "owner" if u["org_id"] == org_id else "reviewer"
    u["side"] = side
    u["actions"] = conn.query(
        "SELECT to_status, requires_note FROM network_status_graph WHERE entity = 'impact_update'"
        " AND from_status = $1 AND actor IN ($2, 'either') ORDER BY to_status", u["status"], side)
    return u


def listing(conn: Connection, *, project_id: str | None = None, org_id: str | None = None,
            status: str | None = None, limit: int = 30, offset: int = 0) -> list[dict]:
    rows = conn.query(
        f"{_SELECT} WHERE ($1::uuid IS NULL OR u.project_id = $1) AND ($2::uuid IS NULL OR u.org_id = $2)"
        f" AND ($3::text IS NULL OR u.status = $3) ORDER BY u.period_end DESC LIMIT $4 OFFSET $5",
        project_id, org_id, status, limit, offset)
    for r in rows:
        r["status_label"] = ST_LABEL[r["status"]]
    return rows


def published_for_project(conn: Connection, project_id: str) -> list[dict]:
    """Relatórios que podem ser mostrados a quem não é parte: somente publicados."""
    return conn.query(
        "SELECT period_start, period_end, summary, outputs, outcomes, limitations, metrics, evidence_count,"
        " published_at FROM impact_updates WHERE project_id = $1 AND status = 'published'"
        " ORDER BY period_end DESC LIMIT 20", project_id)
