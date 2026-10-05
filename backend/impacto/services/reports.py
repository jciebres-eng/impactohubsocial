"""Central de relatórios (§19): executivo, técnico, financeiro, evidências, ODS, ESG, auditoria e conselho.

Estrutura genérica {sections:[{title, kind: kv|table|text, ...}]} para renderizar na interface, exportar CSV e imprimir.
Linguagem controlada: "indicadores REPORTADOS" e "evidência de ALINHAMENTO aos ODS"; nada aqui é rating ESG, certificação ou
prova de causalidade. Dados vêm do banco sob a RLS do solicitante (cada papel só enxerga o que já poderia ver)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from ..db.pq import Connection
from ..http import ApiError

TYPES = {
    "executive": ("Relatório executivo", ("osc", "company", "government", "individual")),
    "technical": ("Relatório técnico do projeto", ("osc",)),
    "financial": ("Relatório financeiro", ("osc", "company", "government", "individual")),
    "evidence": ("Relatório de evidências", ("osc", "company", "government", "individual")),
    "ods": ("Alinhamento aos ODS", ("osc", "company", "government", "individual")),
    "esg": ("Indicadores ESG reportados", ("osc", "company", "government", "individual")),
    "audit": ("Integridade e auditoria", ("osc", "company", "government", "individual", "provider")),
    "board": ("Resumo para conselho/diretoria", ("osc", "company", "government", "individual")),
}
WORDING = ("Valores 'reportados' são informados pelas organizações; 'validados' foram conferidos por outra organização com evidência anexada. "
           "Este relatório não é rating ESG, certificação nem prova de causalidade.")


def kinds_for(kind: str) -> list[dict]:
    return [{"type": k, "title": t} for k, (t, ks) in TYPES.items() if kind in ks]


def _scope(c: Connection, kind: str, org_id: str, project_id: str | None) -> list[dict]:
    if kind == "osc":
        rows = c.query("SELECT id::text AS id, title, status, budget_total_cents, territory, causes, ods, esg_tags FROM projects WHERE org_id = $1"
                       " AND ($2::uuid IS NULL OR id = $2) ORDER BY created_at", org_id, project_id)
    else:
        rows = c.query("SELECT DISTINCT p.id::text AS id, p.title, p.status, p.budget_total_cents, p.territory, p.causes, p.ods, p.esg_tags FROM projects p"
                       " WHERE app_project_investor(p.id) AND ($1::uuid IS NULL OR p.id = $1) ORDER BY p.title", project_id)
    if project_id and not rows:
        raise ApiError(404, "not_found", "Projeto não encontrado no seu escopo")
    return rows


def _money(c_) -> float:
    return round((c_ or 0) / 100, 2)


def _kv(title, items):
    return {"title": title, "kind": "kv", "items": [{"label": k, "value": v} for k, v in items]}


def _table(title, columns, rows):
    return {"title": title, "kind": "table", "columns": columns, "rows": rows}


def _funding(c, pids):
    return c.one("SELECT coalesce(sum(amount_cents) FILTER (WHERE status <> 'cancelled'),0) AS committed, coalesce(sum(amount_cents) FILTER (WHERE status IN ('disbursed','confirmed')),0) AS disbursed,"
                 " coalesce(sum(amount_cents) FILTER (WHERE status = 'confirmed'),0) AS confirmed FROM commitments WHERE project_id = ANY($1::uuid[])"
                 " AND (funder_org_id = app_org() OR osc_org_id = app_org())", pids)


def build(c: Connection, rtype: str, kind: str, org_id: str, project_id: str | None) -> dict:
    if rtype not in TYPES or kind not in TYPES[rtype][1]:
        raise ApiError(404, "unknown_report", "Relatório indisponível para este tipo de organização")
    projects = _scope(c, kind, org_id, project_id)
    pids = [p["id"] for p in projects]
    org = c.one("SELECT org_display(id) AS name, kind FROM organizations WHERE id = $1", org_id)
    sections: list[dict] = []
    fn = _BUILDERS[rtype]
    fn(c, kind, org_id, projects, pids, sections)
    return {"type": rtype, "title": TYPES[rtype][0], "organization": org["name"], "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "scope": {"projects": len(projects), "project_id": project_id}, "sections": sections, "wording": WORDING}


def _executive(c, kind, org_id, projects, pids, sec):
    f = _funding(c, pids)
    ev = c.query("SELECT status, count(*) AS n FROM evidences WHERE project_id = ANY($1::uuid[]) GROUP BY status", pids)
    evd = {r["status"]: r["n"] for r in ev}
    spent = c.scalar("SELECT coalesce(sum(amount_cents),0) FROM expenses WHERE project_id = ANY($1::uuid[])", pids)
    sec.append(_kv("Visão geral", [("Projetos no escopo", len(projects)), ("Orçamento total (R$)", _money(sum(p["budget_total_cents"] for p in projects))),
                                   ("Comprometido (R$)", _money(f["committed"])), ("Desembolsado/declarado (R$)", _money(f["disbursed"])),
                                   ("Confirmado pela OSC (R$)", _money(f["confirmed"])), ("Despesas registradas (R$)", _money(spent)),
                                   ("Evidências aceitas", evd.get("accepted", 0)), ("Evidências em revisão", evd.get("submitted", 0))]))
    sec.append(_table("Projetos", ["Projeto", "Situação", "Território", "Orçamento (R$)"],
                      [[p["title"], p["status"], p["territory"], _money(p["budget_total_cents"])] for p in projects]))
    ind = c.query("SELECT ic.name, ic.unit, pi.target::float AS target, (SELECT value::float FROM indicator_values v WHERE v.project_indicator_id = pi.id AND v.status <> 'rejected'"
                  " ORDER BY measured_on DESC LIMIT 1) AS reported, (SELECT value::float FROM indicator_values v WHERE v.project_indicator_id = pi.id AND v.status = 'validated'"
                  " ORDER BY measured_on DESC LIMIT 1) AS validated FROM project_indicators pi JOIN indicator_catalog ic ON ic.id = pi.indicator_id WHERE pi.project_id = ANY($1::uuid[])", pids)
    if ind:
        sec.append(_table("Indicadores (reportado × validado)", ["Indicador", "Unidade", "Meta", "Último reportado", "Último validado"],
                          [[i["name"], i["unit"], i["target"], i["reported"], i["validated"]] for i in ind]))


def _technical(c, kind, org_id, projects, pids, sec):
    for p in projects:
        d = c.one("SELECT problem, objectives, methodology, beneficiaries_count, starts_on, ends_on FROM projects WHERE id = $1", p["id"])
        sec.append({"title": f"{p['title']} — problema e objetivos", "kind": "text", "text": f"Problema: {d['problem'] or '—'}\n\nObjetivos: {d['objectives'] or '—'}\n\nMetodologia: {d['methodology'] or '—'}"})
        ms = c.query("SELECT seq, title, amount_cents, funded_cents, status, due_on FROM milestones WHERE project_id = $1 ORDER BY seq", p["id"])
        sec.append(_table(f"{p['title']} — marcos", ["#", "Marco", "Valor (R$)", "Financiado (R$)", "Situação", "Prazo"],
                          [[m["seq"], m["title"], _money(m["amount_cents"]), _money(m["funded_cents"]), m["status"], str(m["due_on"] or "")] for m in ms]))
    _evidence(c, kind, org_id, projects, pids, sec)


def _financial(c, kind, org_id, projects, pids, sec):
    f = _funding(c, pids)
    sec.append(_kv("Resumo financeiro", [("Comprometido (R$)", _money(f["committed"])), ("Desembolsado/declarado (R$)", _money(f["disbursed"])), ("Confirmado (R$)", _money(f["confirmed"]))]))
    pay = c.query("SELECT pr.title, p.amount_cents, p.refunded_cents, p.state, p.method, p.reconciliation_status, p.created_at::date AS d FROM payment_records p"
                  " JOIN projects pr ON pr.id = p.project_id WHERE p.project_id = ANY($1::uuid[]) AND (p.funder_org_id = $2 OR p.osc_org_id = $2) ORDER BY p.created_at", pids, org_id)
    sec.append(_table("Pagamentos registrados", ["Projeto", "Valor (R$)", "Estornado (R$)", "Estado", "Forma", "Conciliação", "Data"],
                      [[r["title"], _money(r["amount_cents"]), _money(r["refunded_cents"]), r["state"], r["method"], r["reconciliation_status"], str(r["d"])] for r in pay]))
    exp = c.query("SELECT pr.title, e.description, e.supplier_name, e.amount_cents, e.paid_on, e.status, (e.document_id IS NOT NULL) AS has_receipt FROM expenses e JOIN projects pr ON pr.id = e.project_id"
                  " WHERE e.project_id = ANY($1::uuid[]) ORDER BY e.paid_on", pids)
    sec.append(_table("Despesas", ["Projeto", "Descrição", "Fornecedor", "Valor (R$)", "Data", "Situação", "Comprovante"],
                      [[r["title"], r["description"], r["supplier_name"] or "", _money(r["amount_cents"]), str(r["paid_on"]), r["status"], "sim" if r["has_receipt"] else "não"] for r in exp]))
    byst = c.query("SELECT status, count(*) AS n, coalesce(sum(amount_cents),0) AS total FROM expenses WHERE project_id = ANY($1::uuid[]) GROUP BY status", pids)
    sec.append(_table("Despesas por situação", ["Situação", "Quantidade", "Total (R$)"], [[r["status"], r["n"], _money(r["total"])] for r in byst]))


def _evidence(c, kind, org_id, projects, pids, sec):
    ev = c.query("SELECT pr.title, e.kind, e.title AS etitle, e.occurred_on, e.status, e.indicator_name, e.indicator_value::float AS val FROM evidences e JOIN projects pr ON pr.id = e.project_id"
                 " WHERE e.project_id = ANY($1::uuid[]) ORDER BY e.created_at", pids)
    sec.append(_table("Evidências por etapa", ["Projeto", "Tipo", "Título", "Data", "Situação", "Indicador", "Valor"],
                      [[r["title"], r["kind"], r["etitle"], str(r["occurred_on"] or ""), r["status"], r["indicator_name"] or "", r["val"]] for r in ev]))


def _ods(c, kind, org_id, projects, pids, sec):
    rows = c.query("SELECT g.number, g.name, count(DISTINCT t.project_id) AS projects,"
                   " count(DISTINCT t.project_id) FILTER (WHERE EXISTS (SELECT 1 FROM indicator_values v JOIN project_indicators pi ON pi.id = v.project_indicator_id"
                   "   JOIN indicator_catalog ic ON ic.id = pi.indicator_id WHERE v.project_id = t.project_id AND v.status = 'validated' AND ic.ods = t.ods)) AS with_validated"
                   " FROM project_ods_targets t JOIN ods_goals g ON g.number = t.ods WHERE t.project_id = ANY($1::uuid[]) GROUP BY g.number, g.name ORDER BY g.number", pids)
    sec.append(_table("Projetos por ODS (alinhamento declarado) e com indicador validado", ["ODS", "Nome", "Projetos", "Com indicador validado"],
                      [[r["number"], r["name"], r["projects"], r["with_validated"]] for r in rows]))
    legacy = c.query("SELECT unnest(ods) AS ods, count(*) AS n FROM projects WHERE id = ANY($1::uuid[]) GROUP BY 1 ORDER BY 1", pids)
    sec.append(_table("ODS marcados no projeto (campo livre)", ["ODS", "Projetos"], [[r["ods"], r["n"]] for r in legacy]))
    sec.append({"title": "Como ler", "kind": "text", "text": "'Alinhamento declarado' é a escolha da OSC. Só há 'evidência de alinhamento' quando existe valor de indicador validado por outra organização para aquele ODS."})


def _esg(c, kind, org_id, projects, pids, sec):
    rows = c.query("SELECT coalesce(ic.esg_dimension, '—') AS dim, count(DISTINCT pi.id) AS indicators,"
                   " count(DISTINCT pi.id) FILTER (WHERE EXISTS (SELECT 1 FROM indicator_values v WHERE v.project_indicator_id = pi.id AND v.status <> 'rejected')) AS reported,"
                   " count(DISTINCT pi.id) FILTER (WHERE EXISTS (SELECT 1 FROM indicator_values v WHERE v.project_indicator_id = pi.id AND v.status = 'validated')) AS validated"
                   " FROM project_indicators pi JOIN indicator_catalog ic ON ic.id = pi.indicator_id WHERE pi.project_id = ANY($1::uuid[]) GROUP BY 1 ORDER BY 1", pids)
    sec.append(_table("Indicadores por dimensão (E/S/G)", ["Dimensão", "Indicadores", "Com valor reportado", "Com valor validado"],
                      [[r["dim"], r["indicators"], r["reported"], r["validated"]] for r in rows]))
    tags = c.query("SELECT unnest(esg_tags) AS tag, count(*) AS n FROM projects WHERE id = ANY($1::uuid[]) GROUP BY 1 ORDER BY 2 DESC", pids)
    sec.append(_table("Marcadores ESG dos projetos", ["Marcador", "Projetos"], [[r["tag"], r["n"]] for r in tags]))


def _audit(c, kind, org_id, projects, pids, sec):
    a = c.one("SELECT * FROM audit_verify($1)", org_id)
    sec.append(_kv("Trilha de auditoria da organização", [("Eventos verificados", a["entries"]), ("Cadeia íntegra", "sim" if a["valid"] else f"NÃO (primeiro desvio: {a['first_broken_seq']})")]))
    rows = []
    for p in projects:
        v = c.one("SELECT * FROM ledger_verify($1)", p["id"])
        rows.append([p["title"], v["entries"], "sim" if v["valid"] else f"NÃO ({v['first_broken_seq']})"])
    sec.append(_table("Impact Ledger por projeto", ["Projeto", "Entradas", "Íntegro"], rows))
    sec.append({"title": "Observação", "kind": "text", "text": "A verificação detecta alteração posterior dos registros (cadeia de hashes); não atesta a veracidade do conteúdo registrado."})


def _board(c, kind, org_id, projects, pids, sec):
    _executive(c, kind, org_id, projects, pids, sec)
    org = c.one("SELECT compliance_status, compliance_risk FROM organizations WHERE id = $1", org_id)
    sec.append(_kv("Governança", [("Compliance", org["compliance_status"]), ("Risco declarado pela revisão", org["compliance_risk"] or "não classificado")]))
    pend = c.one("SELECT (SELECT count(*) FROM evidences WHERE project_id = ANY($1::uuid[]) AND status = 'submitted') AS evidences,"
                 " (SELECT count(*) FROM expenses WHERE project_id = ANY($1::uuid[]) AND status = 'questioned') AS expenses,"
                 " (SELECT count(*) FROM payment_records WHERE project_id = ANY($1::uuid[]) AND state IN ('awaiting_confirmation','disputed')) AS payments", pids)
    sec.append(_kv("Pendências", [("Evidências aguardando revisão", pend["evidences"]), ("Despesas questionadas", pend["expenses"]), ("Pagamentos aguardando/em disputa", pend["payments"])]))


_BUILDERS = {"executive": _executive, "technical": _technical, "financial": _financial, "evidence": _evidence, "ods": _ods, "esg": _esg, "audit": _audit, "board": _board}


def to_csv(report: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow([report["title"], report["organization"], report["generated_at"]])
    for s in report["sections"]:
        w.writerow([])
        w.writerow([s["title"]])
        if s["kind"] == "table":
            w.writerow(s["columns"])
            for r in s["rows"]:
                w.writerow([_safe(x) for x in r])
        elif s["kind"] == "kv":
            for it in s["items"]:
                w.writerow([it["label"], _safe(it["value"])])
        else:
            w.writerow([s.get("text", "")])
    w.writerow([])
    w.writerow([report["wording"]])
    return out.getvalue()


def _safe(v):
    """Neutraliza injeção de fórmula em planilhas (CSV injection)."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") and not _is_number(s) else s


def _is_number(s: str) -> bool:
    try:
        float(s.replace(",", "."))
        return True
    except ValueError:
        return False
