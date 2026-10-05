"""Prontidão por finalidade: seis números, cada um com a razão de ser esse número.

ACHADO QUE ORIGINOU ESTE MÓDULO: o diagnóstico da v0.15.0 responde "o quanto este projeto está completo" num score
único de 0 a 100. Isso serve a quem monta o projeto, mas não a quem decide. Um investidor não pergunta "está completo?";
pergunta "está pronto PARA CAPTAR?". Um gestor público pergunta "está pronto PARA EXECUTAR?". São perguntas diferentes
com respostas diferentes sobre o mesmo projeto.

Daí seis prontidões, cada uma com os seus critérios:

    documento · projeto · captação · governança · execução · evidência

REGRA QUE ESTE MÓDULO SE IMPÕE: nenhum número sai daqui sem `detail` dizendo o que o compôs e `blockers` dizendo o que
falta. "Captação: 72%" sem explicação não é informação — é um número mágico que ninguém pode contestar nem corrigir.
Cada critério devolve o que foi verificado, o que foi encontrado e quanto valeu.

A prontidão é DERIVADA: não existe rota que a escreva. O retrato (`readiness_snapshots`) é append-only, de modo que
"estávamos 40% em janeiro e 85% em junho" é verificável, e não uma lembrança.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, Json

ENGINE_VERSION = "readiness@1.0.0"

#: As seis prontidões, com rótulo e a pergunta que cada uma responde. A pergunta é o que a interface mostra.
DIMENSIONS: tuple[tuple[str, str, str], ...] = (
    ("document_readiness", "Documentação", "Os documentos exigidos existem, estão válidos e aprovados?"),
    ("project_readiness", "Projeto", "O projeto está descrito o suficiente para ser avaliado por terceiros?"),
    ("funding_readiness", "Captação", "O projeto está pronto para receber e justificar recursos?"),
    ("governance_readiness", "Governança", "Há pessoas, papéis e responsabilidade definidos?"),
    ("execution_readiness", "Execução", "Há marcos, prazos e cronograma executável?"),
    ("evidence_readiness", "Evidência", "O que for afirmado poderá ser comprovado?"),
)
LABELS = {k: v for k, v, _ in DIMENSIONS}
QUESTIONS = {k: q for k, _, q in DIMENSIONS}

#: Faixas de leitura. Existem para que a interface não invente a sua própria régua em cada tela.
def band(score: float) -> str:
    if score >= 85:
        return "pronto"
    if score >= 65:
        return "quase"
    if score >= 35:
        return "em construção"
    return "inicial"


class _Check:
    """Um critério: o que foi verificado, quanto vale, se passou e por quê."""

    __slots__ = ("key", "label", "weight", "got", "found", "blocker")

    def __init__(self, key: str, label: str, weight: float, got: float, found: str, blocker: str | None = None):
        self.key, self.label, self.weight = key, label, weight
        self.got, self.found, self.blocker = max(0.0, min(1.0, got)), found, blocker

    def as_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "weight": self.weight,
                "score": round(self.got * 100, 1), "found": self.found,
                "points": round(self.got * self.weight, 2), "of": self.weight}


def _score(checks: list[_Check]) -> tuple[float, dict]:
    total = sum(c.weight for c in checks) or 1.0
    got = sum(c.got * c.weight for c in checks)
    pct = round(100 * got / total, 2)
    return pct, {"score": pct, "band": band(pct), "checks": [c.as_dict() for c in checks],
                 "blockers": [c.blocker for c in checks if c.blocker and c.got < 1]}


# ------------------------------------------------------------------------------------------------ coleta

def _facts(conn: Connection, project_id: str | None, org_id: str) -> dict[str, Any]:
    """Lê tudo de uma vez. Uma consulta por assunto, nenhuma por critério — prontidão é tela de abertura."""
    org = conn.one(
        "SELECT o.id::text AS id, coalesce(o.trade_name, o.legal_name) AS name, o.legal_name, o.cnpj,"
        " o.legal_nature, o.uf, o.city, o.kind,"
        " o.compliance_status, o.mission, o.founded_on,"
        " (SELECT count(*) FROM memberships m WHERE m.org_id = o.id) AS members,"
        " (SELECT count(*) FROM memberships m WHERE m.org_id = o.id AND m.role IN ('owner','admin','manager'))"
        "   AS leaders FROM organizations o WHERE o.id = $1", org_id) or {}
    docs = conn.query(
        "SELECT doc_type, status, valid_until, (valid_until IS NOT NULL AND valid_until < current_date) AS expired"
        " FROM documents WHERE org_id = $1 AND deleted_at IS NULL", org_id)
    out: dict[str, Any] = {"org": org, "org_docs": docs, "project": None}
    if not project_id:
        return out
    out["project"] = conn.one(
        "SELECT p.id::text AS id, p.title, p.summary, p.status, p.visibility, p.budget_total_cents, p.territory,"
        " p.causes, p.ods, p.beneficiaries_count, p.starts_on, p.ends_on, p.problem, p.objectives,"
        " p.methodology, p.beneficiaries_description FROM projects p WHERE p.id = $1", project_id)
    out["funding"] = conn.one("SELECT committed_cents, confirmed_cents, disbursed_cents, funders"
                              " FROM project_funding($1)", project_id) or {}
    out["milestones"] = conn.query(
        "SELECT status, due_on, amount_cents FROM milestones WHERE project_id = $1", project_id)
    out["indicators"] = conn.query(
        "SELECT pi.id::text AS id, pi.baseline, pi.target, pi.target_date,"
        " (SELECT count(*) FROM indicator_values v WHERE v.project_indicator_id = pi.id) AS measurements,"
        " (SELECT count(*) FROM indicator_values v WHERE v.project_indicator_id = pi.id AND v.status = 'validated')"
        "   AS validated FROM project_indicators pi WHERE pi.project_id = $1", project_id)
    out["budget_items"] = conn.scalar("SELECT count(*) FROM budget_items WHERE project_id = $1", project_id) or 0
    out["project_docs"] = conn.query(
        "SELECT doc_type, status FROM documents WHERE project_id = $1 AND deleted_at IS NULL", project_id)
    out["evidences"] = conn.scalar(
        "SELECT count(*) FROM evidences WHERE project_id = $1", project_id) or 0
    out["team"] = conn.scalar("SELECT count(*) FROM project_team($1)", project_id) or 0
    out["risks"] = conn.query("SELECT severity, status FROM project_risks WHERE project_id = $1", project_id)
    return out


# ------------------------------------------------------------------------------------------------ as seis dimensões

#: Documentos institucionais que um financiador pede antes de qualquer conversa. A lista não é inventada aqui:
#: é a mesma que o diagnóstico da 0013 usa, e está no catálogo de tipos de documento.
REQUIRED_ORG_DOCS = ("estatuto_social", "ata_eleicao_diretoria", "cnpj_card", "cnd_federal")


def _documents(f: dict) -> tuple[float, dict]:
    docs = f["org_docs"] + (f.get("project_docs") or [])
    by_type: dict[str, list[dict]] = {}
    for d in docs:
        by_type.setdefault(d["doc_type"], []).append(d)
    checks = []
    for t in REQUIRED_ORG_DOCS:
        have = by_type.get(t, [])
        approved = [d for d in have if d["status"] == "approved"]
        valid = [d for d in approved if not d.get("expired")]
        if valid:
            got, found = 1.0, "aprovado e dentro da validade"
        elif approved:
            got, found = 0.5, "aprovado, porém com validade vencida"
        elif have:
            got, found = 0.3, f"enviado, situação: {have[0]['status']}"
        else:
            got, found = 0.0, "não enviado"
        checks.append(_Check(f"doc.{t}", t.replace("_", " ").capitalize(), 20, got, found,
                             None if got == 1 else f"Documento pendente: {t.replace('_', ' ')}"))
    expired = [d for d in docs if d.get("expired")]
    checks.append(_Check("doc.no_expired", "Nenhum documento vencido", 20,
                         0.0 if expired else 1.0,
                         f"{len(expired)} documento(s) vencido(s)" if expired else "nenhum vencido",
                         f"{len(expired)} documento(s) com validade vencida" if expired else None))
    return _score(checks)


def _project(f: dict) -> tuple[float, dict]:
    p = f.get("project")
    if not p:
        return 0.0, {"score": 0.0, "band": "inicial", "checks": [],
                     "blockers": ["Sem projeto: a prontidão de projeto é calculada por projeto"]}
    def text(field: str, label: str, weight: float, minimum: int) -> _Check:
        v = (p.get(field) or "").strip()
        n = len(v)
        got = 0.0 if not n else (1.0 if n >= minimum else round(n / minimum, 2))
        return _Check(f"project.{field}", label, weight, got,
                      "não informado" if not n else f"{n} caracteres (mínimo recomendado: {minimum})",
                      f"{label}: descrever com pelo menos {minimum} caracteres" if got < 1 else None)
    checks = [
        text("summary", "Resumo", 15, 120),
        text("problem", "Problema", 20, 200),
        text("objectives", "Objetivos", 20, 200),
        text("methodology", "Metodologia", 10, 120),
        _Check("project.territory", "Território", 10, 1.0 if p.get("territory") else 0.0,
               p.get("territory") or "não informado", "Informar o território de atuação" if not p.get("territory")
               else None),
        _Check("project.beneficiaries", "Público atendido", 10,
               (0.6 if (p.get("beneficiaries_count") or 0) > 0 else 0.0)
               + (0.4 if (p.get("beneficiaries_description") or "").strip() else 0.0),
               f"{p.get('beneficiaries_count') or 0} pessoas"
               + ("; público descrito" if (p.get("beneficiaries_description") or "").strip() else "; sem descrição"),
               "Estimar o número de pessoas atendidas e descrever o público"
               if not ((p.get("beneficiaries_count") or 0) and (p.get("beneficiaries_description") or "").strip())
               else None),
        _Check("project.causes", "Causas e ODS", 10,
               1.0 if (p.get("causes") and p.get("ods")) else (0.5 if (p.get("causes") or p.get("ods")) else 0.0),
               f"{len(p.get('causes') or [])} causa(s), {len(p.get('ods') or [])} ODS",
               "Vincular causas e ODS" if not (p.get("causes") and p.get("ods")) else None),
        _Check("project.dates", "Período de execução", 5,
               1.0 if (p.get("starts_on") and p.get("ends_on")) else 0.0,
               "definido" if (p.get("starts_on") and p.get("ends_on")) else "incompleto",
               "Definir início e fim" if not (p.get("starts_on") and p.get("ends_on")) else None),
    ]
    return _score(checks)


def _funding(f: dict) -> tuple[float, dict]:
    p = f.get("project")
    if not p:
        return 0.0, {"score": 0.0, "band": "inicial", "checks": [], "blockers": ["Sem projeto"]}
    budget = int(p.get("budget_total_cents") or 0)
    items = int(f.get("budget_items") or 0)
    fund = f.get("funding") or {}
    committed = int(fund.get("committed_cents") or 0)
    checks = [
        _Check("funding.budget", "Orçamento total informado", 25, 1.0 if budget > 0 else 0.0,
               "informado" if budget > 0 else "não informado",
               "Informar o orçamento total" if budget <= 0 else None),
        _Check("funding.items", "Orçamento detalhado por item", 25,
               1.0 if items >= 3 else (round(items / 3, 2) if items else 0.0),
               f"{items} item(ns) de orçamento",
               "Detalhar o orçamento em pelo menos 3 itens" if items < 3 else None),
        _Check("funding.published", "Projeto visível para financiadores", 20,
               1.0 if p.get("visibility") == "published" else 0.0,
               f"visibilidade: {p.get('visibility')}",
               "Publicar o projeto para que apareça a financiadores"
               if p.get("visibility") != "published" else None),
        _Check("funding.measurement", "Indicadores com meta", 20,
               1.0 if any(i["target"] is not None for i in f.get("indicators") or []) else 0.0,
               f"{len(f.get('indicators') or [])} indicador(es)",
               "Definir ao menos um indicador com meta" if not any(
                   i["target"] is not None for i in f.get("indicators") or []) else None),
        # Captação já obtida NÃO é critério de prontidão para captar — seria circular: "está pronto porque já captou".
        _Check("funding.milestones_valued", "Marcos com valor", 10,
               1.0 if any((m.get("amount_cents") or 0) > 0 for m in f.get("milestones") or []) else 0.0,
               f"{sum(1 for m in f.get('milestones') or [] if (m.get('amount_cents') or 0) > 0)} marco(s) com valor",
               "Associar valores aos marcos para desembolso por etapa" if not any(
                   (m.get("amount_cents") or 0) > 0 for m in f.get("milestones") or []) else None),
    ]
    pct, detail = _score(checks)
    detail["committed_cents"] = committed
    detail["note"] = ("Captação já obtida não entra no cálculo: prontidão para captar não pode depender de já ter "
                      "captado.")
    return pct, detail


def _governance(f: dict) -> tuple[float, dict]:
    org = f["org"]
    members, leaders = int(org.get("members") or 0), int(org.get("leaders") or 0)
    checks = [
        _Check("gov.members", "Pessoas na organização", 25,
               1.0 if members >= 3 else round(members / 3, 2), f"{members} pessoa(s)",
               "Cadastrar ao menos 3 pessoas na organização" if members < 3 else None),
        _Check("gov.leaders", "Responsáveis definidos", 25,
               1.0 if leaders >= 2 else (0.5 if leaders == 1 else 0.0), f"{leaders} responsável(is)",
               "Definir ao menos dois responsáveis (evita dependência de uma pessoa)" if leaders < 2 else None),
        _Check("gov.compliance", "Cadastro institucional aprovado", 25,
               1.0 if org.get("compliance_status") == "approved" else
               (0.4 if org.get("compliance_status") in ("in_review", "pending") else 0.0),
               f"situação: {org.get('compliance_status')}",
               "Concluir a análise do cadastro institucional"
               if org.get("compliance_status") != "approved" else None),
        _Check("gov.mission", "Missão declarada", 10, 1.0 if (org.get("mission") or "").strip() else 0.0,
               "declarada" if (org.get("mission") or "").strip() else "não declarada",
               "Declarar a missão da organização" if not (org.get("mission") or "").strip() else None),
        _Check("gov.project_team", "Equipe vinculada ao projeto", 15,
               1.0 if int(f.get("team") or 0) >= 2 else (0.5 if int(f.get("team") or 0) == 1 else 0.0),
               f"{int(f.get('team') or 0)} pessoa(s) na equipe do projeto",
               "Vincular pessoas ao projeto" if int(f.get("team") or 0) < 2 else None),
    ]
    return _score(checks)


def _execution(f: dict) -> tuple[float, dict]:
    p = f.get("project")
    if not p:
        return 0.0, {"score": 0.0, "band": "inicial", "checks": [], "blockers": ["Sem projeto"]}
    ms = f.get("milestones") or []
    dated = [m for m in ms if m.get("due_on")]
    done = [m for m in ms if m.get("status") in ("completed", "verified")]
    risks = [r for r in (f.get("risks") or []) if r.get("status") not in ("resolved", "closed")]
    checks = [
        _Check("exec.milestones", "Marcos definidos", 30,
               1.0 if len(ms) >= 3 else (round(len(ms) / 3, 2) if ms else 0.0), f"{len(ms)} marco(s)",
               "Definir ao menos 3 marcos" if len(ms) < 3 else None),
        _Check("exec.dates", "Marcos com prazo", 25,
               round(len(dated) / len(ms), 2) if ms else 0.0,
               f"{len(dated)} de {len(ms)} com prazo",
               "Dar prazo a todos os marcos" if ms and len(dated) < len(ms) else
               ("Definir marcos com prazo" if not ms else None)),
        _Check("exec.period", "Período definido", 15,
               1.0 if (p.get("starts_on") and p.get("ends_on")) else 0.0,
               "definido" if (p.get("starts_on") and p.get("ends_on")) else "incompleto",
               "Definir início e fim da execução" if not (p.get("starts_on") and p.get("ends_on")) else None),
        _Check("exec.progress", "Execução em andamento", 15,
               round(len(done) / len(ms), 2) if ms else 0.0, f"{len(done)} de {len(ms)} concluído(s)", None),
        # Risco registrado AUMENTA a prontidão: quem mapeou risco está mais pronto que quem não olhou.
        _Check("exec.risks_mapped", "Riscos mapeados", 15, 1.0 if (f.get("risks") or []) else 0.0,
               f"{len(f.get('risks') or [])} risco(s) registrado(s), {len(risks)} em aberto",
               "Registrar os riscos conhecidos do projeto" if not (f.get("risks") or []) else None),
    ]
    return _score(checks)


def _evidence(f: dict) -> tuple[float, dict]:
    inds = f.get("indicators") or []
    measured = [i for i in inds if int(i["measurements"] or 0) > 0]
    validated = [i for i in inds if int(i["validated"] or 0) > 0]
    checks = [
        _Check("ev.indicators", "Indicadores definidos", 25,
               1.0 if len(inds) >= 2 else (0.5 if inds else 0.0), f"{len(inds)} indicador(es)",
               "Definir ao menos dois indicadores" if len(inds) < 2 else None),
        _Check("ev.baseline", "Linha de base registrada", 20,
               round(sum(1 for i in inds if i["baseline"] is not None) / len(inds), 2) if inds else 0.0,
               f"{sum(1 for i in inds if i['baseline'] is not None)} de {len(inds)} com linha de base",
               "Registrar a linha de base: sem ela não há como mostrar mudança" if inds and not all(
                   i["baseline"] is not None for i in inds) else ("Definir indicadores" if not inds else None)),
        _Check("ev.measured", "Indicadores medidos", 25,
               round(len(measured) / len(inds), 2) if inds else 0.0,
               f"{len(measured)} de {len(inds)} com medição",
               "Lançar medições dos indicadores" if inds and len(measured) < len(inds) else None),
        _Check("ev.validated", "Medições validadas", 20,
               round(len(validated) / len(inds), 2) if inds else 0.0,
               f"{len(validated)} de {len(inds)} com medição validada",
               "Validar as medições lançadas" if inds and len(validated) < len(inds) else None),
        _Check("ev.files", "Evidências anexadas", 10,
               1.0 if int(f.get("evidences") or 0) >= 1 else 0.0,
               f"{int(f.get('evidences') or 0)} evidência(s)",
               "Anexar evidência do que foi executado" if not int(f.get("evidences") or 0) else None),
    ]
    return _score(checks)


_CALC = {"document_readiness": _documents, "project_readiness": _project, "funding_readiness": _funding,
         "governance_readiness": _governance, "execution_readiness": _execution, "evidence_readiness": _evidence}

#: Peso de cada prontidão no número geral. Documentação e evidência pesam mais porque são o que sustenta qualquer
#: afirmação da plataforma a terceiros — e é o que distingue "projeto bonito" de "projeto comprovável".
WEIGHTS = {"document_readiness": 20, "project_readiness": 18, "funding_readiness": 16,
           "governance_readiness": 14, "execution_readiness": 14, "evidence_readiness": 18}


def evaluate(conn: Connection, *, org_id: str, project_id: str | None = None) -> dict[str, Any]:
    """Calcula as seis prontidões. NÃO grava — leitura é barata e não deve sujar o histórico."""
    f = _facts(conn, project_id, org_id)
    dims: dict[str, Any] = {}
    scores: dict[str, float] = {}
    blockers: list[dict] = []
    for key, fn in _CALC.items():
        pct, detail = fn(f)
        scores[key] = pct
        detail["label"] = LABELS[key]
        detail["question"] = QUESTIONS[key]
        dims[key] = detail
        for b in detail.get("blockers") or []:
            blockers.append({"dimension": key, "label": LABELS[key], "blocker": b})
    overall = round(sum(scores[k] * WEIGHTS[k] for k in scores) / sum(WEIGHTS.values()), 2)
    return {"engine_version": ENGINE_VERSION, "org_id": org_id, "project_id": project_id,
            "overall": overall, "band": band(overall), "scores": scores, "dimensions": dims,
            "blockers": blockers, "weights": WEIGHTS,
            "note": "Cada número vem dos critérios listados em dimensions[].checks. Não há ajuste manual."}


def snapshot(conn: Connection, *, org_id: str, project_id: str | None = None) -> dict[str, Any]:
    """Calcula e GRAVA o retrato. Append-only: serve a "como estávamos em janeiro?"."""
    r = evaluate(conn, org_id=org_id, project_id=project_id)
    row = conn.one(
        "INSERT INTO readiness_snapshots(org_id, project_id, document_readiness, project_readiness,"
        " funding_readiness, governance_readiness, execution_readiness, evidence_readiness, overall, detail,"
        " blockers, engine_version) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,$12)"
        " RETURNING id::text AS id, computed_at",
        org_id, project_id, r["scores"]["document_readiness"], r["scores"]["project_readiness"],
        r["scores"]["funding_readiness"], r["scores"]["governance_readiness"],
        r["scores"]["execution_readiness"], r["scores"]["evidence_readiness"], r["overall"],
        Json(r["dimensions"]), Json(r["blockers"]), ENGINE_VERSION)
    return {**r, "snapshot_id": row["id"], "computed_at": row["computed_at"]}


def history(conn: Connection, *, org_id: str, project_id: str | None = None, limit: int = 24) -> list[dict]:
    """Série histórica das prontidões. É o que permite dizer "melhoramos" com número, não com adjetivo."""
    return conn.query(
        "SELECT id::text AS id, project_id::text AS project_id, document_readiness, project_readiness,"
        " funding_readiness, governance_readiness, execution_readiness, evidence_readiness, overall,"
        " engine_version, computed_at FROM readiness_snapshots"
        " WHERE org_id = $1 AND ($2::uuid IS NULL OR project_id = $2)"
        " ORDER BY computed_at DESC LIMIT $3", org_id, project_id, limit)
