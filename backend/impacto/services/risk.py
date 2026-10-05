"""Risco e antifraude: SINAIS determinísticos e explicáveis para revisão humana.

Princípios (docs/RISK_FRAUD.md): nunca declara "fraude" — registra sinal, severidade e evidência; quem decide é a administração
(revisão obrigatória com justificativa). 'blocked' só por decisão humana registrada. Todos os sinais usam apenas dados que a
plataforma já guarda (hash de documento, despesas, orçamento, cotações, vínculos de usuários).
Executa em contexto de sistema (job `risk_scan` e rota administrativa).
"""
from __future__ import annotations

import statistics

from ..db.pq import Connection, Json

DETECTORS: list = []


def detector(fn):
    DETECTORS.append(fn)
    return fn


def _emit(c: Connection, *, org_id: str, project_id: str | None, signal_type: str, severity: str, key: str, summary: str, details: dict) -> int:
    return c.run("INSERT INTO risk_signals(org_id, project_id, signal_type, severity, dedupe_key, summary, details)"
                 " VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb) ON CONFLICT (dedupe_key) DO NOTHING",
                 org_id, project_id, signal_type, severity, key[:300], summary[:500], Json(details)) or 0


@detector
def duplicate_document_hash(c: Connection, org: str | None) -> int:
    """Mesmo arquivo (sha256) usado como comprovante/evidência por organizações diferentes."""
    n = 0
    rows = c.query("SELECT d.sha256, array_agg(DISTINCT d.org_id::text) AS orgs, array_agg(DISTINCT d.id::text) AS docs FROM documents d"
                   " WHERE d.deleted_at IS NULL AND (EXISTS (SELECT 1 FROM expenses e WHERE e.document_id = d.id)"
                   "   OR EXISTS (SELECT 1 FROM evidences v WHERE v.document_id = d.id))"
                   " GROUP BY d.sha256 HAVING count(DISTINCT d.org_id) > 1")
    for r in rows:
        for o in r["orgs"]:
            if org and o != org:
                continue
            n += _emit(c, org_id=o, project_id=None, signal_type="duplicate_document_hash", severity="high", key=f"dup_hash:{r['sha256']}:{o}",
                       summary="Arquivo idêntico usado como comprovante por mais de uma organização",
                       details={"sha256_prefix": r["sha256"][:12], "organizations_involved": len(r["orgs"]), "documents": len(r["docs"])})
    return n


@detector
def evidence_reuse(c: Connection, org: str | None) -> int:
    """Mesmo documento anexado a 2+ despesas/evidências da mesma organização."""
    n = 0
    rows = c.query("SELECT org_id::text AS org_id, project_id::text AS project_id, document_id::text AS doc, count(*) AS n FROM ("
                   " SELECT org_id, project_id, document_id FROM expenses WHERE document_id IS NOT NULL"
                   " UNION ALL SELECT org_id, project_id, document_id FROM evidences WHERE document_id IS NOT NULL) x"
                   " GROUP BY org_id, project_id, document_id HAVING count(*) > 1")
    for r in rows:
        if org and r["org_id"] != org:
            continue
        n += _emit(c, org_id=r["org_id"], project_id=r["project_id"], signal_type="evidence_reuse", severity="medium", key=f"reuse:{r['doc']}",
                   summary="O mesmo documento sustenta mais de uma despesa/evidência", details={"uses": r["n"]})
    return n


@detector
def duplicate_expense(c: Connection, org: str | None) -> int:
    n = 0
    rows = c.query("SELECT org_id::text AS org_id, project_id::text AS project_id, supplier_cnpj, amount_cents, paid_on, count(*) AS n FROM expenses"
                   " WHERE supplier_cnpj IS NOT NULL GROUP BY org_id, project_id, supplier_cnpj, amount_cents, paid_on HAVING count(*) > 1")
    for r in rows:
        if org and r["org_id"] != org:
            continue
        n += _emit(c, org_id=r["org_id"], project_id=r["project_id"], signal_type="duplicate_expense", severity="medium",
                   key=f"dup_exp:{r['project_id']}:{r['supplier_cnpj']}:{r['amount_cents']}:{r['paid_on']}",
                   summary="Despesas com mesmo fornecedor, valor e data", details={"occurrences": r["n"], "amount_cents": r["amount_cents"], "paid_on": str(r["paid_on"])})
    return n


@detector
def expense_over_budget_item(c: Connection, org: str | None) -> int:
    n = 0
    rows = c.query("SELECT b.id::text AS id, b.org_id::text AS org_id, b.project_id::text AS project_id, b.total_cents, sum(e.amount_cents) AS spent"
                   " FROM budget_items b JOIN expenses e ON e.budget_item_id = b.id GROUP BY b.id HAVING sum(e.amount_cents) > b.total_cents")
    for r in rows:
        if org and r["org_id"] != org:
            continue
        over = round(100 * (r["spent"] - r["total_cents"]) / r["total_cents"], 1) if r["total_cents"] else 100.0
        n += _emit(c, org_id=r["org_id"], project_id=r["project_id"], signal_type="expense_over_budget_item", severity="high" if over > 20 else "medium",
                   key=f"over:{r['id']}", summary="Gasto acima do previsto no item de orçamento", details={"over_pct": over, "budget_cents": r["total_cents"], "spent_cents": r["spent"]})
    return n


@detector
def price_outlier(c: Connection, org: str | None) -> int:
    """Cotação escolhida acima do limite da política em relação à mediana das cotações."""
    n = 0
    rows = c.query("SELECT r.id::text AS id, r.org_id::text AS org_id, r.project_id::text AS project_id, q.amount_cents AS chosen,"
                   " coalesce(p.outlier_pct, 30)::float AS lim FROM procurement_requests r JOIN quotations q ON q.id = r.selected_quotation_id"
                   " LEFT JOIN procurement_policies p ON p.org_id = r.org_id WHERE r.status IN ('decided','exception_approved')")
    for r in rows:
        if org and r["org_id"] != org:
            continue
        amounts = [x["amount_cents"] for x in c.query("SELECT amount_cents FROM quotations WHERE request_id = $1", r["id"])]
        if len(amounts) < 3:
            continue
        med = statistics.median(amounts)
        dev = 100 * (r["chosen"] - med) / med if med else 0
        if dev > r["lim"]:
            n += _emit(c, org_id=r["org_id"], project_id=r["project_id"], signal_type="price_outlier", severity="medium", key=f"price:{r['id']}",
                       summary="Cotação escolhida possivelmente acima do padrão das cotações", details={"deviation_pct": round(dev, 1), "limit_pct": r["lim"]})
    return n


@detector
def related_accounts(c: Connection, org: str | None) -> int:
    """Mesmo usuário com vínculo em financiador e OSC que têm candidatura entre si (possível conflito de interesse)."""
    n = 0
    rows = c.query("SELECT DISTINCT a.osc_org_id::text AS osc, a.funder_org_id::text AS funder, m1.user_id::text AS uid FROM applications a"
                   " JOIN memberships m1 ON m1.org_id = a.osc_org_id JOIN memberships m2 ON m2.org_id = a.funder_org_id AND m2.user_id = m1.user_id"
                   " WHERE a.funder_org_id IS NOT NULL AND a.status <> 'withdrawn'")
    for r in rows:
        if org and r["osc"] != org:
            continue
        n += _emit(c, org_id=r["osc"], project_id=None, signal_type="related_accounts", severity="high", key=f"related:{r['osc']}:{r['funder']}:{r['uid']}",
                   summary="Um mesmo usuário tem vínculo com a OSC e com o financiador da candidatura",
                   details={"funder_org_id": r["funder"], "note": "pode ser legítimo (ex.: conselheiro); exige declaração de conflito"})
    return n


@detector
def supplier_is_party(c: Connection, org: str | None) -> int:
    n = 0
    rows = c.query("SELECT e.org_id::text AS org_id, e.project_id::text AS project_id, e.supplier_cnpj, count(*) AS n FROM expenses e"
                   " WHERE e.supplier_cnpj IS NOT NULL AND (e.supplier_cnpj = (SELECT cnpj FROM organizations WHERE id = e.org_id)"
                   "   OR EXISTS (SELECT 1 FROM commitments cm JOIN organizations f ON f.id = cm.funder_org_id WHERE cm.project_id = e.project_id AND f.cnpj = e.supplier_cnpj))"
                   " GROUP BY e.org_id, e.project_id, e.supplier_cnpj")
    for r in rows:
        if org and r["org_id"] != org:
            continue
        n += _emit(c, org_id=r["org_id"], project_id=r["project_id"], signal_type="supplier_is_party", severity="high", key=f"party:{r['project_id']}:{r['supplier_cnpj']}",
                   summary="Fornecedor tem o mesmo CNPJ da própria OSC ou de um financiador do projeto", details={"expenses": r["n"]})
    return n


@detector
def quotes_below_policy(c: Connection, org: str | None) -> int:
    n = 0
    rows = c.query("SELECT e.org_id::text AS org_id, e.project_id::text AS project_id, count(*) AS n FROM expenses e"
                   " JOIN procurement_policies p ON p.org_id = e.org_id WHERE e.procurement_request_id IS NULL AND e.amount_cents >= p.quote_threshold_cents"
                   " AND p.quote_threshold_cents > 0 GROUP BY e.org_id, e.project_id")
    for r in rows:
        if org and r["org_id"] != org:
            continue
        n += _emit(c, org_id=r["org_id"], project_id=r["project_id"], signal_type="quotes_below_policy", severity="low", key=f"noquote:{r['project_id']}:{r['n']}",
                   summary="Despesas acima do limite da política sem pedido de cotações vinculado", details={"expenses": r["n"]})
    return n


def level_for(open_by_sev: dict) -> tuple[str, str]:
    high, med, low = (open_by_sev.get(k, 0) for k in ("high", "medium", "low"))
    if high:
        return "manual_review", f"{high} sinal(is) de severidade alta aguardando revisão humana"
    if med >= 3:
        return "high", f"{med} sinais de severidade média em aberto"
    if med or low:
        return "medium", f"{med + low} sinal(is) de baixa/média severidade em aberto"
    return "low", "Nenhum sinal em aberto"


def recompute(c: Connection, org: str | None = None) -> int:
    """Recalcula o nível de cada organização com sinais. 'blocked' (decisão humana) nunca é alterado aqui."""
    rows = c.query("SELECT org_id::text AS org_id, severity, count(*) AS n FROM risk_signals WHERE status = 'open'"
                   " AND ($1::uuid IS NULL OR org_id = $1) GROUP BY org_id, severity", org)
    by: dict[str, dict] = {}
    for r in rows:
        by.setdefault(r["org_id"], {})[r["severity"]] = r["n"]
    existing = {r["org_id"]: r["level"] for r in c.query("SELECT org_id::text AS org_id, level FROM risk_assessments WHERE ($1::uuid IS NULL OR org_id = $1)", org)}
    cnt = 0
    for oid in set(by) | set(existing):
        if existing.get(oid) == "blocked":
            continue
        lvl, why = level_for(by.get(oid, {}))
        c.run("INSERT INTO risk_assessments(org_id, level, rationale, open_signals, updated_at) VALUES ($1,$2,$3,$4,now())"
              " ON CONFLICT (org_id) DO UPDATE SET level = EXCLUDED.level, rationale = EXCLUDED.rationale, open_signals = EXCLUDED.open_signals,"
              " updated_at = now() WHERE risk_assessments.level <> 'blocked'", oid, lvl, why, sum(by.get(oid, {}).values()))
        cnt += 1
    return cnt


def scan(c: Connection, org: str | None = None) -> dict:
    found = {fn.__name__: fn(c, org) for fn in DETECTORS}
    assessed = recompute(c, org)
    return {"new_signals": found, "total_new": sum(found.values()), "organizations_assessed": assessed}


def ensure_not_blocked(c: Connection, org_id: str) -> None:
    from ..http import ApiError
    if c.scalar("SELECT app_org_blocked($1)", org_id):
        raise ApiError(423, "org_blocked", "Esta organização está com restrição operacional pendente de revisão da administração")
