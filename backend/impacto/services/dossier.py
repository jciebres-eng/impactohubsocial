"""Dossiê longitudinal do projeto (v0.30.0, ADR-361): UMA leitura, somente-leitura, para quem financia ou acompanha.

O que é: a composição das peças que já existem — identidade e situação, prontidão ("IMPACTO Ready", 15 critérios), marcos e
obrigações, evidências por estado com qualidade e atualidade, indicadores (reportado × validado, por série, com método e
unidade), proveniência, diligências pendentes, aportes registrados/confirmados — cada bloco com ORIGEM (tabela/motor),
ATUALIDADE (data do dado mais recente) e LACUNAS declaradas. Nenhum número nasce aqui: tudo é contagem ou leitura do que
está gravado; o que não há fica `unknown`, nunca zero.

O que NÃO é: nota, ranking, score de impacto, parecer, auditoria independente ou prova de liquidação financeira. O bloco
`what_this_is_not` vai junto na resposta para que a interface o mostre.

Visibilidade: a RLS de `projects` decide quem enxerga; a função não escolhe o que mostrar por perfil — mostra o que a sessão
pode ler. A OSC dona vê o próprio dossiê (é o que o financiador vai ver — sem assimetria).
"""
from __future__ import annotations

from typing import Any

from ..clock import today
from ..db.pq import Connection
from ..network import control_tower as CT

ENGINE_VERSION = "dossier@1.0"

WHAT_THIS_IS_NOT = [
    "não é nota nem ranking: cada bloco é contagem ou leitura do que está registrado, com a origem ao lado",
    "'validado' significa conferido por outra organização no escopo registrado — não auditoria independente",
    "aceitar evidência ou validar indicador não move dinheiro: repasse é instrução do pagador + confirmação de quem recebe",
    "o hash prova integridade do arquivo, não a veracidade do fato",
    "'unknown' é lacuna declarada; a plataforma não preenche com zero",
    "delta entre medições não implica causalidade; o contexto territorial e a metodologia estão ao lado da série",
]

STALE_DAYS = 90


def _age(d) -> int | None:
    if d is None:
        return None
    if hasattr(d, "date"):
        d = d.date()
    return (today() - d).days


def _block(source: str, latest=None, **data) -> dict[str, Any]:
    age = _age(latest)
    return {"source": source, "latest_at": latest, "age_days": age,
            "freshness": "unknown" if age is None else ("stale" if age > STALE_DAYS else "recent"), **data}


def build(c: Connection, project_id: str, viewer_org_id: str | None) -> dict[str, Any] | None:
    p = c.one("SELECT p.id::text AS id, p.title, p.status, p.territory, p.causes, p.ods, p.beneficiaries_count, p.starts_on, p.ends_on,"
              " p.budget_total_cents, p.created_at, p.updated_at, p.org_id::text AS org_id, o.legal_name AS org_name,"
              " o.compliance_status AS org_compliance FROM projects p JOIN organizations o ON o.id = p.org_id WHERE p.id = $1", project_id)
    if not p:
        return None
    gaps: list[str] = []

    # ---- prontidão (motor existente, 15 critérios, unknown como terceiro estado)
    ready = CT.ready(c, project_id)
    readiness = _block("project_ready_facts() / control_tower.ready", p["updated_at"],
                       state=ready["state"] if ready else "unknown",
                       met=sum(1 for x in (ready or {}).get("criteria", []) if x["status"] == "met"),
                       unmet=sum(1 for x in (ready or {}).get("criteria", []) if x["status"] == "unmet"),
                       unknown=sum(1 for x in (ready or {}).get("criteria", []) if x["status"] == "unknown"),
                       criteria=(ready or {}).get("criteria", []), hash=(ready or {}).get("hash"))
    if not ready:
        gaps.append("readiness")

    # ---- marcos do projeto e obrigações contratuais
    ms = c.query("SELECT seq, title, status, due_on, amount_cents, funded_cents FROM milestones WHERE project_id = $1 ORDER BY seq", project_id)
    by_ms: dict[str, int] = {}
    for m in ms:
        by_ms[m["status"]] = by_ms.get(m["status"], 0) + 1
    obl = c.query("SELECT ob.kind, ob.status, ob.due_on FROM agreement_obligations ob JOIN signed_agreements a ON a.id = ob.agreement_id"
                  " WHERE a.project_id = $1", project_id)
    by_obl: dict[str, int] = {}
    for o in obl:
        k = f"{o['kind']}:{o['status']}"
        by_obl[k] = by_obl.get(k, 0) + 1
    milestones = _block("milestones + agreement_obligations (contrato como regra, ADR-336)",
                        max([m["due_on"] for m in ms if m["due_on"]], default=None),
                        total=len(ms), by_status=by_ms, overdue_obligations=sum(1 for o in obl if o["status"] == "overdue"),
                        obligations_by_kind_status=by_obl, items=ms)
    if not ms:
        gaps.append("milestones")

    # ---- evidências por estado, com qualidade (método/consentimento/documento) e atualidade
    ev = c.query("SELECT status, method, consent_basis, document_id IS NOT NULL AS has_document, kind, occurred_on, created_at, version"
                 " FROM evidences WHERE project_id = $1", project_id)
    by_ev: dict[str, int] = {}
    quality = {"with_document": 0, "method_known": 0, "consent_known": 0}
    for e in ev:
        by_ev[e["status"]] = by_ev.get(e["status"], 0) + 1
        quality["with_document"] += 1 if e["has_document"] else 0
        quality["method_known"] += 1 if e["method"] != "unknown" else 0
        quality["consent_known"] += 1 if e["consent_basis"] != "unknown" else 0
    evidences = _block("evidences + evidence_events (ADR-360)", max([e["created_at"] for e in ev], default=None),
                       total=len(ev), by_status=by_ev, quality=quality,
                       classification={"validated": by_ev.get("accepted", 0), "declared": by_ev.get("submitted", 0) + by_ev.get("needs_info", 0),
                                       "contested": by_ev.get("contested", 0) + by_ev.get("under_review", 0),
                                       "rejected": by_ev.get("rejected", 0), "superseded": by_ev.get("superseded", 0)})
    if not ev:
        gaps.append("evidences")

    # ---- indicadores: série por indicador, reportado × validado, método e unidade; sem média, sem causalidade
    series = c.query("SELECT pi.id::text AS project_indicator_id, ic.name, ic.unit, pi.method, pi.baseline::float AS baseline, pi.target::float AS target,"
                     " pi.target_date FROM project_indicators pi JOIN indicator_catalog ic ON ic.id = pi.indicator_id WHERE pi.project_id = $1"
                     " ORDER BY ic.name", project_id)
    latest_measure = None
    for s_ in series:
        vals = c.query("SELECT value::float AS value, measured_on, status, source_kind, evidence_id IS NOT NULL AS has_evidence"
                       " FROM indicator_values WHERE project_indicator_id = $1 ORDER BY measured_on", s_["project_indicator_id"])
        s_["reported"] = [v for v in vals if v["status"] == "reported"]
        s_["validated"] = [v for v in vals if v["status"] == "validated"]
        s_["rejected"] = sum(1 for v in vals if v["status"] == "rejected")
        s_["method_declared"] = bool(s_["method"])
        s_["method_changes"] = c.query("SELECT changed_at, old_method, new_method, reason FROM indicator_method_changes"
                                       " WHERE project_indicator_id = $1 ORDER BY changed_at", s_["project_indicator_id"])
        s_["comparable"] = not s_["method_changes"]
        if vals:
            latest_measure = max(latest_measure or vals[-1]["measured_on"], vals[-1]["measured_on"])
    indicators = _block("project_indicators + indicator_values (0004/0053: validado exige evidência e outra organização)", latest_measure,
                        total=len(series), with_validated_values=sum(1 for s_ in series if s_["validated"]),
                        without_any_value=sum(1 for s_ in series if not s_["reported"] and not s_["validated"]), series=series)
    if not series:
        gaps.append("indicators")

    # ---- aportes e repasses: registros das partes, nunca saldo (ADR-338)
    com = c.query("SELECT status, amount_cents FROM commitments WHERE project_id = $1 AND status <> 'cancelled'", project_id)
    by_c: dict[str, int] = {}
    for x in com:
        by_c[x["status"]] = by_c.get(x["status"], 0) + int(x["amount_cents"])
    pay = c.one("SELECT count(*) FILTER (WHERE pt.status = 'registered') AS registered, count(*) FILTER (WHERE pt.status = 'confirmed') AS confirmed"
                " FROM payout_transfers pt JOIN allocation_payouts ap ON ap.id = pt.payout_id JOIN signed_agreements a ON a.id = ap.agreement_id"
                " WHERE a.project_id = $1", project_id)
    funding = _block("commitments (pledged/disbursed/confirmed) + payout_transfers (registrado por quem paga, confirmado por quem recebe)", None,
                     commitments_cents_by_status=by_c, transfers={"registered": int(pay["registered"] or 0), "confirmed": int(pay["confirmed"] or 0)},
                     notice="valores são registros das partes; a plataforma não custodia nem liquida (ADR-284/337)")

    # ---- diligências e pendências
    pend = c.one("SELECT count(*) FILTER (WHERE status IN ('submitted','needs_info','contested','under_review')) AS evidence_pending,"
                 " (SELECT count(*) FROM indicator_values iv WHERE iv.project_id = $1 AND iv.status = 'reported') AS values_awaiting_validation,"
                 " (SELECT count(*) FROM agreement_obligations ob JOIN signed_agreements a ON a.id = ob.agreement_id WHERE a.project_id = $1 AND ob.status = 'overdue') AS overdue"
                 " FROM evidences WHERE project_id = $1", project_id)
    diligence = _block("derivado dos blocos acima", None, evidence_pending=int(pend["evidence_pending"] or 0),
                       values_awaiting_validation=int(pend["values_awaiting_validation"] or 0), obligations_overdue=int(pend["overdue"] or 0))

    # ---- trilha no tempo: transições e snapshots (LONGITUDINAL_TRACKING.md)
    trail = c.one("SELECT (SELECT count(*) FROM project_transitions t WHERE t.project_id = $1) AS transitions,"
                  " (SELECT count(*) FROM project_snapshots s WHERE s.project_id = $1) AS snapshots,"
                  " (SELECT max(l.at) FROM ledger_entries l WHERE l.project_id = $1) AS last_ledger_at", project_id)
    timeline = _block("project_transitions + project_snapshots + ledger_entries (append-only, hash encadeado)", trail["last_ledger_at"],
                      transitions=int(trail["transitions"] or 0), snapshots=int(trail["snapshots"] or 0))

    return {
        "engine": ENGINE_VERSION, "generated_at": today().isoformat(),
        "project": {k: p[k] for k in ("id", "title", "status", "territory", "causes", "ods", "beneficiaries_count", "starts_on", "ends_on",
                                     "budget_total_cents", "org_name", "org_compliance")},
        "viewer_is_owner": viewer_org_id == p["org_id"],
        "readiness": readiness, "milestones": milestones, "evidences": evidences, "indicators": indicators,
        "funding": funding, "diligence": diligence, "timeline": timeline,
        "gaps": gaps, "what_this_is_not": WHAT_THIS_IS_NOT,
        "rules_version": {"readiness_criteria": len(CT.READY_CRITERIA), "evidence_states": "0070", "indicator_provenance": "0053"},
    }
