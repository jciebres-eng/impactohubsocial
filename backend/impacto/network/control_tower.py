"""Torres de controle (v0.26.0) e o estado verificável "Projeto IMPACTO Ready".

Tese: quem controla recursos prefere operar pela plataforma porque ela responde, com registro e não com
opinião, a cadeia "meu capital → onde está → para quem → para quê → o que foi executado → que evidência
existe → o que mudou → o que está atrasado → que riscos apareceram → o que precisa da minha decisão".

Três regras valem para tudo aqui:
  * Só leitura. Nenhuma torre muda estado — ela aponta para a tela onde a decisão é tomada.
  * Contagem desconhecida NÃO é zero. Quando um fato não pôde ser lido (RLS, tabela vazia por falta de
    módulo), o critério fica `unknown`, e o estado "IMPACTO Ready" nunca é concedido com desconhecidos.
  * "IMPACTO Ready" não é selo pago nem nota: é a lista de critérios com a evidência (contagem e
    tabela) de cada um, com hash do material — qualquer parte confere o mesmo resultado.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ..db.pq import Connection

READY_ENGINE = "impacto-ready@1.0.0"

# (chave, rótulo, pergunta que o critério responde, tabela de origem)
READY_CRITERIA: tuple[tuple[str, str, str, str], ...] = (
    ("identity", "Identidade validada", "Alguém que responde pela organização confirmou identidade com documento?", "identity_verifications"),
    ("organization", "Organização validada", "A organização passou pela conformidade da plataforma?", "organizations.compliance_status"),
    ("documents", "Documentação mínima", "Estatuto, cartão CNPJ e ata da diretoria estão validados e no prazo?", "documents"),
    ("diagnosis", "Diagnóstico realizado", "Há diagnóstico completo (ou aplicado) ligado ao projeto?", "diagnoses"),
    ("budget", "Orçamento estruturado", "O orçamento tem itens, não só um total?", "budget_items"),
    ("needs", "Necessidades identificadas", "O problema está descrito e há necessidades registradas?", "projects.problem / project_needs"),
    ("ods", "ODS mapeados", "O projeto declara ao menos um ODS?", "projects.ods"),
    ("indicators", "Indicadores definidos", "Há indicadores com linha de base?", "project_indicators"),
    ("evidence", "Evidências disponíveis", "Há evidência aceita por outra parte?", "evidences"),
    ("responsibles", "Responsáveis identificados", "Há responsabilidade formal atribuída ao projeto ou equipe registrada?", "responsibility_assignments / project_team"),
    ("risks", "Riscos avaliados", "O registro de riscos foi preenchido?", "project_risks"),
    ("professionals", "Profissionais envolvidos", "Há profissional ou organização parceira ligada ao projeto?", "project_team"),
    ("governance", "Governança definida", "A organização tem mais de uma pessoa com papel de direção?", "memberships"),
    ("history", "Histórico longitudinal", "O razão do projeto tem registros encadeados?", "ledger_entries"),
    ("accountability", "Prestação de contas estruturada", "Há relatório de impacto analisado ou despesas documentadas?", "impact_updates / expenses"),
)


def _n(v: Any) -> int | None:
    return None if v is None else int(v)


def ready(conn: Connection, project_id: str) -> dict | None:
    """Estado "IMPACTO Ready" de um projeto que o chamador enxerga. Devolve None se não enxerga."""
    # Visibilidade decidida pela RLS de `projects` NESTA sessão (a função abaixo é SECURITY DEFINER e repete
    # o mesmo teste por dentro — duas barreiras, uma regra).
    if not conn.scalar("SELECT 1 FROM projects WHERE id = $1", project_id):
        return None
    f = conn.scalar("SELECT project_ready_facts($1)", project_id)
    if f is None:
        return None
    if isinstance(f, str):
        f = json.loads(f)

    def crit(key: str, met: bool | None, evidence: dict) -> dict:
        label, question, source = next((c[1], c[2], c[3]) for c in READY_CRITERIA if c[0] == key)
        return {"key": key, "label": label, "question": question, "source": source,
                "status": "unknown" if met is None else ("met" if met else "unmet"), "evidence": evidence}

    lvl = _n(f.get("owner_identity_level"))
    comp = f.get("org_compliance_status")
    docs_req, docs_ok = _n(f.get("docs_required_present")), _n(f.get("docs_validated"))
    diag = _n(f.get("diagnoses_complete"))
    items = _n(f.get("budget_items"))
    needs, problem = _n(f.get("needs")), f.get("problem_declared")
    ods = _n(f.get("ods"))
    ind, ind_b = _n(f.get("indicators")), _n(f.get("indicators_with_baseline"))
    ev = _n(f.get("evidences_accepted"))
    resp, team = _n(f.get("responsibles")), _n(f.get("team"))
    risks = _n(f.get("risks"))
    prof = _n(f.get("professionals"))
    leaders = _n(f.get("leaders"))
    ledger = _n(f.get("ledger_entries"))
    upd, exp_doc, exp = _n(f.get("impact_updates_reviewed")), _n(f.get("expenses_documented")), _n(f.get("expenses"))

    criteria = [
        crit("identity", None if lvl is None else lvl >= 3, {"level_rank": lvl, "minimum": "document"}),
        crit("organization", None if comp is None else comp == "approved", {"compliance_status": comp}),
        crit("documents", None if docs_req is None else docs_req >= 3, {"required_types_validated": docs_req, "validated_in_date": docs_ok, "required": 3}),
        crit("diagnosis", None if diag is None else diag >= 1, {"complete_or_applied": diag, "any": _n(f.get("diagnoses_any"))}),
        crit("budget", None if items is None else items >= 1, {"items": items, "total_cents": _n(f.get("budget_total_cents"))}),
        crit("needs", None if (needs is None or problem is None) else (bool(problem) and needs >= 1), {"problem_declared": problem, "needs": needs}),
        crit("ods", None if ods is None else ods >= 1, {"ods": ods}),
        crit("indicators", None if ind is None else (ind >= 1 and (ind_b or 0) >= 1), {"indicators": ind, "with_baseline": ind_b,
             "values_reported": _n(f.get("indicator_values_reported")), "values_validated": _n(f.get("indicator_values_validated"))}),
        crit("evidence", None if ev is None else ev >= 1, {"accepted": ev, "submitted": _n(f.get("evidences_submitted"))}),
        crit("responsibles", None if (resp is None and team is None) else ((resp or 0) >= 1 or (team or 0) >= 1), {"formal_assignments": resp, "team": team}),
        crit("risks", None if risks is None else risks >= 1, {"registered": risks, "open_high_or_critical": _n(f.get("risks_open_critical"))}),
        crit("professionals", None if prof is None else prof >= 1, {"linked": prof}),
        crit("governance", None if leaders is None else leaders >= 2, {"leaders": leaders, "minimum": 2}),
        crit("history", None if ledger is None else ledger >= 1, {"ledger_entries": ledger, "since": f.get("ledger_first_at")}),
        crit("accountability", None if (upd is None and exp_doc is None) else ((upd or 0) >= 1 or ((exp_doc or 0) >= 1 and exp_doc == exp)),
             {"impact_updates_reviewed": upd, "expenses": exp, "expenses_documented": exp_doc}),
    ]
    met = sum(1 for c in criteria if c["status"] == "met")
    unknown = sum(1 for c in criteria if c["status"] == "unknown")
    unmet = [c["key"] for c in criteria if c["status"] == "unmet"]
    state = "ready" if met == len(criteria) else ("not_assessable" if unknown and met + unknown == len(criteria) else "in_progress")
    material = json.dumps({"engine": READY_ENGINE, "project_id": project_id,
                           "criteria": [(c["key"], c["status"], c["evidence"]) for c in criteria]}, sort_keys=True, default=str)
    return {
        "engine_version": READY_ENGINE, "project_id": project_id, "state": state,
        "met": met, "unmet": len(unmet), "unknown": unknown, "total": len(criteria), "unmet_keys": unmet,
        "criteria": criteria, "computed_at": f.get("computed_at"),
        "evaluation_hash": hashlib.sha256(material.encode()).hexdigest(),
        "note": ("Estado verificável, não selo: cada critério aponta a tabela e a contagem que o sustenta. "
                 "Critério desconhecido não conta como zero, e o estado 'ready' exige todos os critérios atendidos."),
    }


# ---------------------------------------------------------------------------------------------- financiador
def funder(conn: Connection, *, org_id: str) -> dict:
    """Meu capital → onde está → para quem → finalidade → executado → evidência → mudou → atrasado → riscos → decidir."""
    from ..trust import contract_rules
    projetos = conn.query(
        "SELECT p.id::text AS project_id, p.title, p.status, p.territory, p.causes, p.ods, o.legal_name AS osc_name, o.id::text AS osc_id,"
        " sum(cm.amount_cents) FILTER (WHERE cm.status <> 'cancelled') AS committed_cents,"
        " sum(cm.amount_cents) FILTER (WHERE cm.status IN ('disbursed','confirmed')) AS disbursed_cents,"
        " sum(cm.amount_cents) FILTER (WHERE cm.status = 'confirmed') AS confirmed_cents,"
        " (SELECT coalesce(sum(e.amount_cents),0) FROM expenses e WHERE e.project_id = p.id) AS spent_cents,"
        " (SELECT coalesce(sum(e.amount_cents),0) FROM expenses e WHERE e.project_id = p.id AND e.status = 'validated') AS validated_spent_cents,"
        " (SELECT count(*) FROM milestones m WHERE m.project_id = p.id) AS milestones,"
        " (SELECT count(*) FROM milestones m WHERE m.project_id = p.id AND m.status = 'accepted') AS milestones_accepted,"
        " (SELECT count(*) FROM milestones m WHERE m.project_id = p.id AND m.due_on < current_date AND m.status NOT IN ('accepted','rejected')) AS milestones_overdue,"
        " (SELECT count(*) FROM evidences ev WHERE ev.project_id = p.id AND ev.status = 'accepted') AS accepted_evidences,"
        " (SELECT count(*) FROM evidences ev WHERE ev.project_id = p.id AND ev.status = 'submitted') AS pending_evidences,"
        " (SELECT max(l.at) FROM ledger_entries l WHERE l.project_id = p.id) AS last_activity,"
        " (SELECT count(*) FROM ledger_entries l WHERE l.project_id = p.id AND l.at > now() - interval '30 days') AS changes_30d,"
        " p.beneficiaries_count, p.budget_total_cents"
        " FROM commitments cm JOIN projects p ON p.id = cm.project_id JOIN organizations o ON o.id = p.org_id"
        " WHERE cm.funder_org_id = $1 GROUP BY p.id, o.id ORDER BY max(cm.created_at) DESC", org_id)
    for p in projetos:
        p["purpose"] = {"causes": p.pop("causes"), "ods": p.pop("ods"), "beneficiaries": p.pop("beneficiaries_count")}
        p["ready"] = _ready_summary(conn, p["project_id"])
    tot = {k: sum(int(r[k] or 0) for r in projetos) for k in ("committed_cents", "disbursed_cents", "confirmed_cents", "spent_cents",
                                                                 "validated_spent_cents", "accepted_evidences", "pending_evidences",
                                                                 "milestones", "milestones_accepted", "milestones_overdue")}
    tot["projects"] = len(projetos)
    tot["in_transit_cents"] = tot["committed_cents"] - tot["disbursed_cents"]
    # Dinheiro que a plataforma NÃO tem: nada aqui é saldo. É compromisso, desembolso e gasto declarado/validado.
    obrig = contract_rules.pending_for(conn, org_id, limit=50)
    candidaturas = conn.query(
        "SELECT a.id::text AS id, a.status, a.requested_cents, a.submitted_at, p.title AS project_title, o.legal_name AS osc_name"
        " FROM applications a JOIN projects p ON p.id = a.project_id JOIN organizations o ON o.id = a.osc_org_id"
        " WHERE a.funder_org_id = $1 AND a.status IN ('submitted','screening','due_diligence') ORDER BY a.submitted_at NULLS LAST LIMIT 20", org_id)
    relatorios = conn.query(
        "SELECT u.id::text AS id, u.project_id::text AS project_id, p.title AS project_title, u.period_start, u.period_end, u.status, u.submitted_at"
        " FROM impact_updates u JOIN projects p ON p.id = u.project_id"
        " WHERE u.status IN ('submitted','under_review') AND app_project_supporter(u.project_id)"
        " ORDER BY u.submitted_at NULLS LAST LIMIT 20")
    evidencias = conn.query(
        "SELECT e.id::text AS id, e.project_id::text AS project_id, p.title AS project_title, e.title, e.kind, e.occurred_on"
        " FROM evidences e JOIN projects p ON p.id = e.project_id"
        " WHERE e.status = 'submitted' AND app_project_investor(e.project_id) ORDER BY e.occurred_on DESC NULLS LAST LIMIT 20")
    atrasos = conn.query(
        "SELECT m.id::text AS id, m.project_id::text AS project_id, p.title AS project_title, m.title, m.due_on, m.status,"
        " (current_date - m.due_on) AS days_late"
        " FROM milestones m JOIN projects p ON p.id = m.project_id"
        " WHERE app_project_investor(m.project_id) AND m.due_on < current_date AND m.status NOT IN ('accepted','rejected')"
        " ORDER BY m.due_on LIMIT 30")
    # O registro de riscos é da OSC (RLS: só ela lê as linhas). O financiador vê a CONTAGEM de riscos altos/críticos
    # em aberto por projeto, pela mesma função de fatos do IMPACTO Ready — e pede o detalhe à OSC.
    riscos = []
    for p in projetos:
        f = conn.scalar("SELECT project_ready_facts($1)", p["project_id"])
        f = json.loads(f) if isinstance(f, str) else (f or {})
        n = int(f.get("risks_open_critical") or 0)
        if n:
            riscos.append({"project_id": p["project_id"], "project_title": p["title"], "open_high_or_critical": n,
                           "registered": int(f.get("risks") or 0), "source": "project_risks (contagem; detalhe é da OSC)"})
    sinais = conn.query(
        "SELECT s.id::text AS id, s.org_id::text AS org_id, s.signal_type, s.severity, s.summary, s.detected_at"
        " FROM risk_signals s WHERE s.status = 'open' AND s.project_id IN (SELECT project_id FROM commitments WHERE funder_org_id = $1)"
        " ORDER BY s.detected_at DESC LIMIT 20", org_id)
    mudancas = conn.query(
        "SELECT l.project_id::text AS project_id, p.title AS project_title, l.entry_type, l.amount_cents, l.at"
        " FROM ledger_entries l JOIN projects p ON p.id = l.project_id"
        " WHERE app_project_investor(l.project_id) AND l.at > now() - interval '30 days' ORDER BY l.at DESC LIMIT 40")
    decisoes = (
        [{"kind": "obligation", "ref": o["agreement_id"], "title": o["title"], "due_on": o["due_on"], "overdue": o["overdue"],
          "link": f"/acordos/{o['agreement_id']}"} for o in obrig]
        + [{"kind": "application", "ref": a["id"], "title": f"Decidir candidatura: {a['project_title']} ({a['osc_name']})",
            "due_on": None, "overdue": False, "link": f"/candidaturas/{a['id']}"} for a in candidaturas]
        + [{"kind": "impact_update", "ref": r["id"], "title": f"Analisar relatório de impacto: {r['project_title']}",
            "due_on": None, "overdue": False, "link": "/relatorios-impacto"} for r in relatorios]
        + [{"kind": "evidence", "ref": e["id"], "title": f"Analisar evidência: {e['title']} ({e['project_title']})",
            "due_on": None, "overdue": False, "link": f"/projetos/{e['project_id']}"} for e in evidencias]
    )
    return {
        "capital": tot, "projects": projetos, "changes_30d": mudancas, "delays": atrasos,
        "risks": {"project_risks": riscos, "signals": sinais}, "decisions": decisoes,
        "counts": {"decisions": len(decisoes), "delays": len(atrasos), "risks": len(riscos) + len(sinais), "changes_30d": len(mudancas)},
        "note": ("A plataforma não custodia nem movimenta recursos: 'comprometido', 'desembolsado' e 'confirmado' são registros "
                 "das partes, e 'gasto validado' é despesa com documento aceita por quem acompanha."),
    }


def _ready_summary(conn: Connection, project_id: str) -> dict | None:
    r = ready(conn, project_id)
    if not r:
        return None
    return {"state": r["state"], "met": r["met"], "unknown": r["unknown"], "total": r["total"], "unmet_keys": r["unmet_keys"]}


# ---------------------------------------------------------------------------------------------- governo
def government(conn: Connection, *, org_id: str, territory: str | None = None) -> dict:
    """Meu território → recursos → programas → editais → OSCs → projetos → indicadores → atrasos → lacunas."""
    from ..economics import programs as PG
    org = conn.one("SELECT uf, city, ibge_code, territories FROM organizations WHERE id = $1", org_id) or {}
    prefixo = territory or (f"BR-{org['uf']}" if org.get("uf") else "BR")
    linhas = conn.query("SELECT * FROM gov_territory_overview($1, 3)", prefixo)
    for r in linhas:
        for k in ("project_id", "osc_id"):
            r[k] = str(r[k])
    programas = conn.query(
        "SELECT id::text AS id, title, status, sphere, instrument, budget_total_cents, territories, causes, starts_on, ends_on"
        " FROM programs WHERE owner_org_id = $1 ORDER BY created_at DESC LIMIT 20", org_id)
    editais = conn.query(
        "SELECT id::text AS id, title, status, sphere, budget_total_cents, territories, causes, opens_at, closes_at,"
        " (SELECT count(*) FROM applications a WHERE a.call_id = c.id) AS applications"
        " FROM calls c WHERE c.owner_org_id = $1 ORDER BY c.created_at DESC LIMIT 20", org_id)
    oscs: dict[str, dict] = {}
    for r in linhas:
        o = oscs.setdefault(r["osc_id"], {"osc_id": r["osc_id"], "osc_name": r["osc_name"], "compliance": r["osc_compliance"],
                                          "projects": 0, "committed_cents": 0, "professionals": 0})
        o["projects"] += 1
        o["committed_cents"] += int(r["committed_cents"] or 0)
        o["professionals"] += int(r["professionals"] or 0)
    tot = {k: sum(int(r[k] or 0) for r in linhas) for k in ("budget_total_cents", "committed_cents", "disbursed_cents", "confirmed_cents",
                                                               "spent_cents", "validated_spent_cents", "indicators", "values_reported",
                                                               "values_validated", "evidences_accepted", "milestones", "milestones_overdue")}
    tot["projects"] = len(linhas)
    tot["oscs"] = len(oscs)
    atrasados = [r for r in linhas if int(r["milestones_overdue"] or 0) > 0]
    por_causa: dict[str, dict] = {}
    for r in linhas:
        for c in (r["causes"] or ["nao_informada"]):
            x = por_causa.setdefault(c, {"cause": c, "projects": 0, "committed_cents": 0, "values_validated": 0, "values_reported": 0})
            x["projects"] += 1
            x["committed_cents"] += int(r["committed_cents"] or 0)
            x["values_validated"] += int(r["values_validated"] or 0)
            x["values_reported"] += int(r["values_reported"] or 0)
    lacunas = PG.territorial_gap(conn, territory_prefix=prefixo)
    return {
        "territory": {"prefix": prefixo, "uf": org.get("uf"), "city": org.get("city"), "ibge_code": org.get("ibge_code")},
        "k_anonymity": {"min_group": 3, "suppressed": len(linhas) == 0},
        "totals": tot, "programs": programas, "calls": editais, "oscs": sorted(oscs.values(), key=lambda o: -o["committed_cents"]),
        "projects": linhas, "by_cause": sorted(por_causa.values(), key=lambda x: -x["projects"]),
        "indicators": {"reported": tot["values_reported"], "validated": tot["values_validated"],
                       "note": "declarado é o que a OSC informou; validado é o que outra parte conferiu com evidência"},
        "delays": [{"project_id": r["project_id"], "title": r["title"], "osc_name": r["osc_name"], "milestones_overdue": r["milestones_overdue"]}
                   for r in atrasados],
        "gaps": lacunas,
        "note": ("Só projetos PUBLICADOS entram; território com menos de 3 projetos publicados não sai linha a linha "
                 "(k-anonimato). Indicadores aparecem como contagens de medições, nunca como dado de pessoa."),
    }
