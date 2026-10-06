"""Programa: a unidade que financiador e governo administram.

POR QUE A ENTIDADE EXISTE (SAAS_ECONOMIC_AUDIT.md §1 item 1)

Dois motivos, um de defeito e um de produto.

**O defeito:** os planos anunciavam um limite chamado `programs` e esse limite era aplicado contra
`calls` (editais) — o produto vendia uma entidade que não existia.

**O produto:** o mapa de valor desta rodada diz, textualmente, que "projeto é pequeno; programa conecta
orçamento, oportunidades, projetos, organizações, território, contratos, indicadores, evidências,
resultados e impacto — e é o programa que financiadores e governos realmente querem administrar".

TRÊS DECISÕES QUE VALEM REGISTRO

1. **Programa referencia; não duplica.** O edital continua sendo `calls` e o projeto continua sendo
   `projects`, de quem os criou. `program_calls` e `program_projects` são vínculos. Criar cópias
   produziria duas verdades sobre o mesmo edital.
2. **Declarado e apurado são colunas diferentes.** `budget_total_cents` e `allocated_cents` são
   declarados pela dona. Comprometido, desembolsado, executado e **comprovado** vêm de
   `program_financials()`, que lê `commitments`, `project_funding()` e `expenses`. A diferença entre
   executado e comprovado é a pergunta que o mapa de valor manda a plataforma responder.
3. **Nada aqui cobra.** Programa é produto. A monetização está em `billable.py`, depois da auditoria
   legal — regra dos documentos: "não implementar paywall antes de implementar o valor que justifica o
   paywall".
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection
from ..http import forbidden, not_found, unprocessable
from ..network import notify

STATUSES = ("draft", "open", "in_execution", "suspended", "closed", "archived")
OPEN = ("draft", "open", "in_execution", "suspended")
ST_LABEL = {"draft": "rascunho", "open": "aberto", "in_execution": "em execução",
            "suspended": "suspenso", "closed": "encerrado", "archived": "arquivado"}
#: Papéis de um projeto dentro de um programa. `declined` fica registrado de propósito: o financiador
#: precisa saber o que recusou, e a OSC precisa saber que foi avaliada.
PROJECT_ROLES = ("candidate", "selected", "funded", "monitored", "declined", "withdrawn")
ROLE_LABEL = {"candidate": "candidato", "selected": "selecionado", "funded": "financiado",
              "monitored": "acompanhado", "declined": "recusado", "withdrawn": "retirado"}
VISIBILITY = ("organization", "network", "public")


def graph(conn: Connection) -> list[dict]:
    """A máquina de estados como dado, para a interface desenhar os botões a partir dela."""
    return conn.query("SELECT from_status, to_status, actor, requires_note, note"
                      " FROM program_status_graph ORDER BY from_status, to_status")


def create(conn: Connection, *, org_id: str, actor: str | None, title: str, summary: str,
           objective: str, description: str | None = None, budget_total_cents: int | None = None,
           currency: str = "BRL", territories: list[str] | None = None,
           causes: list[str] | None = None, ods: list[int] | None = None,
           sphere: str | None = None, instrument: str | None = None,
           starts_on: Any = None, ends_on: Any = None) -> dict:
    row = conn.one(
        "INSERT INTO programs(owner_org_id, title, summary, objective, description, budget_total_cents,"
        " currency, territories, causes, ods, sphere, instrument, starts_on, ends_on, created_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)"
        " RETURNING id::text AS id, status, created_at",
        org_id, title, summary, objective, description, budget_total_cents, currency,
        territories or [], causes or [], ods or [], sphere, instrument, starts_on, ends_on, actor)
    # v0.20.0 — `Program.created` estava declarado e nunca era gravado. Só o FATO: criar um
    # programa ainda não envolve ninguém de fora, logo não há a quem avisar.
    notify.fact_only(conn, event="Program.created", org_id=org_id, actor_user_id=actor,
                     ref_type="program", ref_id=row["id"], payload={"title": title})
    return {**row, "status_label": ST_LABEL[row["status"]]}


def update(conn: Connection, *, program_id: str, org_id: str, **fields: Any) -> dict:
    """Edita o que é declarado. Situação e datas derivadas não passam por aqui."""
    allowed = ("title", "summary", "objective", "description", "budget_total_cents", "currency",
               "territories", "causes", "ods", "sphere", "instrument", "starts_on", "ends_on",
               "visibility")
    sets, args = [], []
    for k in allowed:
        if k in fields and fields[k] is not None:
            args.append(fields[k])
            sets.append(f"{k} = ${len(args)}")
    if not sets:
        raise unprocessable("Nada a alterar")
    args += [program_id, org_id]
    row = conn.one(f"UPDATE programs SET {', '.join(sets)} WHERE id = ${len(args)-1}"
                   f" AND owner_org_id = ${len(args)} RETURNING id::text AS id, status", *args)
    if not row:
        raise not_found("Programa")
    return {**row, "status_label": ST_LABEL[row["status"]]}


def transition(conn: Connection, *, program_id: str, org_id: str, actor: str | None,
               to_status: str, reason: str | None = None, admin: bool = False) -> dict:
    """Move a situação. O gatilho no banco é quem recusa o que não está no grafo."""
    p = conn.one("SELECT owner_org_id::text AS owner_org_id, status, title FROM programs WHERE id = $1",
                 program_id)
    if not p:
        raise not_found("Programa")
    if not admin and p["owner_org_id"] != org_id:
        raise forbidden("Apenas a organização dona move o programa")
    edge = conn.one("SELECT actor, requires_note FROM program_status_graph"
                    " WHERE from_status = $1 AND to_status = $2", p["status"], to_status)
    if not edge:
        options = [r["to_status"] for r in conn.query(
            "SELECT to_status FROM program_status_graph WHERE from_status = $1 ORDER BY 1", p["status"])]
        raise unprocessable(f"De '{ST_LABEL.get(p['status'], p['status'])}' não é possível ir para "
                            f"'{ST_LABEL.get(to_status, to_status)}'",
                            {"de": p["status"], "possiveis": options}, code="invalid_transition")
    if edge["actor"] == "platform" and not admin:
        raise forbidden("Esta transição é da administração da plataforma")
    if edge["requires_note"] and len(reason or "") < 10:
        raise unprocessable("Esta transição exige motivo com ao menos 10 caracteres",
                            {"campo": "reason"}, code="reason_required")
    row = conn.one("UPDATE programs SET status = $1, closed_reason = coalesce($2, closed_reason)"
                   " WHERE id = $3 RETURNING id::text AS id, status, published_at, closed_at",
                   to_status, reason, program_id)
    _EVENT = {"open": "Program.opened", "in_execution": "Program.in_execution",
              "suspended": "Program.suspended", "closed": "Program.closed"}
    notify.org_event(conn, event=_EVENT.get(to_status, "Program.closed"), org_id=p["owner_org_id"],
                     title=f"Programa '{p['title']}' agora está {ST_LABEL[to_status]}",
                     body=reason, ref_type="program", ref_id=program_id, min_role="member",
                     action_label="Abrir programa", link=f"/programas/{program_id}",
                     priority="high" if to_status == "suspended" else "normal")
    return {**row, "status_label": ST_LABEL[row["status"]]}


# ---------------------------------------------------------------------------- vínculos
def add_call(conn: Connection, *, program_id: str, call_id: str, org_id: str, actor: str | None) -> dict:
    """Pendura um edital da própria organização no programa. O gatilho confere a propriedade."""
    conn.run("INSERT INTO program_calls(program_id, call_id, org_id, added_by) VALUES ($1,$2,$3,$4)"
             " ON CONFLICT (program_id, call_id) DO NOTHING", program_id, call_id, org_id, actor)
    return {"program_id": program_id, "call_id": call_id}


def remove_call(conn: Connection, *, program_id: str, call_id: str, org_id: str) -> dict:
    n = conn.run("DELETE FROM program_calls WHERE program_id = $1 AND call_id = $2 AND org_id = $3",
                 program_id, call_id, org_id)
    if not n:
        raise not_found("Vínculo entre programa e edital")
    return {"removed": n}


def set_project(conn: Connection, *, program_id: str, project_id: str, org_id: str, role: str,
                actor: str | None, allocated_cents: int | None = None, note: str | None = None) -> dict:
    """Põe (ou move) um projeto no programa, com o papel que ele tem ali.

    Um projeto pode ser candidato, selecionado, financiado, acompanhado, recusado ou retirado. O papel
    é do PROGRAMA sobre o projeto — não muda a situação do projeto, que é da OSC que o executa.
    """
    if role not in PROJECT_ROLES:
        raise unprocessable(f"Papel inválido: {role}", {"possiveis": list(PROJECT_ROLES)})
    if not conn.one("SELECT 1 FROM projects WHERE id = $1", project_id):
        raise not_found("Projeto")
    # `Program.project_linked` e `Program.project_role_changed` são fatos DIFERENTES, e a operação
    # abaixo é um upsert: sem esta leitura, entrar num programa e mudar de papel dentro dele viravam
    # o mesmo registro. Por isso `Program.project_linked` estava declarado e nunca acontecia.
    ja_estava = bool(conn.one("SELECT 1 FROM program_projects WHERE program_id = $1"
                              " AND project_id = $2", program_id, project_id))
    row = conn.one(
        "INSERT INTO program_projects(program_id, project_id, org_id, role, allocated_cents, note, added_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7)"
        " ON CONFLICT (program_id, project_id) DO UPDATE SET role = excluded.role,"
        " allocated_cents = coalesce(excluded.allocated_cents, program_projects.allocated_cents),"
        " note = coalesce(excluded.note, program_projects.note)"
        " RETURNING project_id::text AS project_id, role, allocated_cents",
        program_id, project_id, org_id, role, allocated_cents, note, actor)
    # Quem executa o projeto precisa saber que entrou (ou saiu) de um programa: é informação que muda
    # a obrigação dele. Por isso o aviso vai para a equipe do PROJETO, não para a dona do programa.
    evento = "Program.project_role_changed" if ja_estava else "Program.project_linked"
    notify.project_event(conn, event=evento, project_id=project_id,
                         org_id=org_id,
                         title=f"Seu projeto agora é {ROLE_LABEL[role]} em um programa",
                         body=note, ref_type="program", ref_id=program_id,
                         action_label="Ver programa", link=f"/programas/{program_id}",
                         dedupe_parts=(evento, program_id, project_id, role))
    from . import value_ledger
    value_ledger.record(conn, event_type="program.projects_screened", org_id=org_id, units=1,
                        project_id=project_id, program_id=program_id, subject_type="project",
                        subject_id=project_id, metrics={"role": role})
    return {**row, "role_label": ROLE_LABEL[row["role"]]}


def add_indicator(conn: Connection, *, program_id: str, org_id: str, indicator_id: str,
                  actor: str | None, target_value: float | None = None, target_date: Any = None,
                  baseline_value: float | None = None, baseline_date: Any = None,
                  baseline_source: str | None = None, note: str | None = None) -> dict:
    """Acrescenta indicador ao programa.

    Linha de base **exige fonte** (CHECK no banco). Mesmo princípio de
    `territory_needs.people_estimate`: número de partida sem fonte é número inventado, e o programa
    inteiro passa a medir contra ele.
    """
    if baseline_value is not None and not baseline_source:
        raise unprocessable("Linha de base exige a fonte de onde veio",
                            {"campo": "baseline_source"}, code="source_required")
    row = conn.one(
        "INSERT INTO program_indicators(program_id, org_id, indicator_id, target_value, target_date,"
        " baseline_value, baseline_date, baseline_source, note, created_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)"
        " ON CONFLICT (program_id, indicator_id) DO UPDATE SET target_value = excluded.target_value,"
        " target_date = excluded.target_date, note = excluded.note"
        " RETURNING id::text AS id, indicator_id::text AS indicator_id",
        program_id, org_id, indicator_id, target_value, target_date, baseline_value, baseline_date,
        baseline_source, note, actor)
    return row


def add_need(conn: Connection, *, program_id: str, need_id: str, org_id: str, actor: str | None) -> dict:
    """Liga o programa a uma necessidade de território: é o que permite a análise de lacuna."""
    conn.run("INSERT INTO program_needs(program_id, need_id, org_id, added_by) VALUES ($1,$2,$3,$4)"
             " ON CONFLICT (program_id, need_id) DO NOTHING", program_id, need_id, org_id, actor)
    return {"program_id": program_id, "need_id": need_id}


# ---------------------------------------------------------------------------- leitura
def get(conn: Connection, *, program_id: str, org_id: str | None) -> dict:
    """O programa com o que ele agrega e o dinheiro APURADO ao lado do declarado.

    A RLS decide se a linha aparece; aqui não há `WHERE org_id` adicional, de propósito — duplicar a
    regra de visibilidade em Python é como as duas versões divergem.
    """
    p = conn.one(
        "SELECT p.id::text AS id, p.owner_org_id::text AS owner_org_id,"
        " coalesce(o.trade_name, o.legal_name) AS owner_name, p.title, p.summary, p.description,"
        " p.objective, p.budget_total_cents, p.currency, p.territories, p.causes, p.ods, p.sphere,"
        " p.instrument, p.starts_on, p.ends_on, p.status, p.visibility, p.published_at, p.closed_at,"
        " p.closed_reason, p.created_at, p.updated_at"
        " FROM programs p JOIN organizations o ON o.id = p.owner_org_id WHERE p.id = $1", program_id)
    if not p:
        raise not_found("Programa")
    fin = conn.one("SELECT * FROM program_financials($1)", program_id) or {}
    return {
        **p,
        "status_label": ST_LABEL.get(p["status"], p["status"]),
        "is_owner": org_id is not None and p["owner_org_id"] == org_id,
        # Declarado e apurado lado a lado, nomeados como tais. Misturá-los num só número chamado
        # "captado" é o erro que o invariante dos três estágios financeiros existe para impedir.
        "declared": {"budget_total_cents": p["budget_total_cents"],
                     "allocated_cents": fin.get("allocated_cents")},
        "measured": {k: fin.get(k) for k in ("committed_cents", "disbursed_cents", "confirmed_cents",
                                             "spent_cents", "evidenced_cents")},
        "counts": {"projects_total": fin.get("projects_total"), "projects_funded": fin.get("projects_funded"),
                   "calls": conn.scalar("SELECT count(*) FROM program_calls WHERE program_id = $1", program_id),
                   "indicators": conn.scalar("SELECT count(*) FROM program_indicators WHERE program_id = $1",
                                             program_id),
                   "needs": conn.scalar("SELECT count(*) FROM program_needs WHERE program_id = $1", program_id)},
        "calls": conn.query(
            "SELECT c.id::text AS id, c.title, c.status, c.closes_at, c.budget_total_cents"
            " FROM program_calls pc JOIN calls c ON c.id = pc.call_id"
            " WHERE pc.program_id = $1 ORDER BY c.closes_at NULLS LAST", program_id),
        "projects": conn.query(
            "SELECT pp.project_id::text AS project_id, pr.title, pr.status, pr.territory, pp.role,"
            " pp.allocated_cents, pp.note, coalesce(o.trade_name, o.legal_name) AS org_name"
            " FROM program_projects pp JOIN projects pr ON pr.id = pp.project_id"
            " JOIN organizations o ON o.id = pr.org_id"
            " WHERE pp.program_id = $1 ORDER BY pp.role, pr.title", program_id),
        "indicators": conn.query(
            "SELECT pi.id::text AS id, ic.code, ic.name, ic.unit, ic.result_kind, pi.target_value,"
            " pi.target_date, pi.baseline_value, pi.baseline_date, pi.baseline_source, pi.note"
            " FROM program_indicators pi JOIN indicator_catalog ic ON ic.id = pi.indicator_id"
            " WHERE pi.program_id = $1 ORDER BY ic.result_kind, ic.name", program_id),
        "needs": conn.query(
            "SELECT n.id::text AS id, n.title, n.territory, n.cause, n.priority, n.status,"
            " n.people_estimate, n.source_name"
            " FROM program_needs pn JOIN territory_needs n ON n.id = pn.need_id"
            " WHERE pn.program_id = $1 ORDER BY n.priority DESC, n.title", program_id),
    }


def mine(conn: Connection, *, org_id: str, status: str | None = None, limit: int = 25,
         offset: int = 0) -> dict:
    rows = conn.query(
        "SELECT p.id::text AS id, p.title, p.summary, p.status, p.visibility, p.budget_total_cents,"
        " p.currency, p.territories, p.starts_on, p.ends_on, p.created_at,"
        " (SELECT count(*) FROM program_projects pp WHERE pp.program_id = p.id) AS projects,"
        " (SELECT count(*) FROM program_calls pc WHERE pc.program_id = p.id) AS calls"
        " FROM programs p WHERE p.owner_org_id = $1 AND ($2::text IS NULL OR p.status = $2)"
        " ORDER BY p.created_at DESC LIMIT $3 OFFSET $4", org_id, status, limit + 1, offset)
    more = len(rows) > limit
    return {"items": [{**r, "status_label": ST_LABEL.get(r["status"], r["status"])} for r in rows[:limit]],
            "has_more": more, "limit": limit, "offset": offset}


def public_feed(conn: Connection, *, territory: str | None = None, cause: str | None = None,
                limit: int = 25, offset: int = 0) -> dict:
    """Programas que a dona escolheu publicar.

    Um único lugar filtra o que é público — mesmo princípio de `marketplace.PUBLIC_STATES`. A política
    de RLS também filtra; a redundância é deliberada, porque esta é uma rota sem sessão.
    """
    rows = conn.query(
        "SELECT p.id::text AS id, p.title, p.summary, p.objective, p.territories, p.causes, p.ods,"
        " p.budget_total_cents, p.currency, p.starts_on, p.ends_on, p.status, p.published_at,"
        " coalesce(o.trade_name, o.legal_name) AS owner_name, o.kind AS owner_kind"
        " FROM programs p JOIN organizations o ON o.id = p.owner_org_id"
        " WHERE p.visibility = 'public' AND p.published_at IS NOT NULL AND p.status <> 'suspended'"
        "   AND ($1::text IS NULL OR $1 = ANY (p.territories))"
        "   AND ($2::text IS NULL OR $2 = ANY (p.causes))"
        " ORDER BY p.published_at DESC LIMIT $3 OFFSET $4", territory, cause, limit + 1, offset)
    more = len(rows) > limit
    return {"items": [{**r, "status_label": ST_LABEL.get(r["status"], r["status"])} for r in rows[:limit]],
            "has_more": more, "limit": limit, "offset": offset}


def result_chain(conn: Connection, *, project_id: str) -> dict:
    """A cadeia de resultado do projeto, com a FORÇA de cada elo declarada.

    A honestidade está em `link_type`, que vem da v0.15.0 e já tinha CHECK no banco:
    `validated_causality` exige evidência **mais** revisor de outra organização **mais** nota;
    `hypothesis` e `inference` não exigem nada. Esta função não promove nenhum elo — devolve o que
    está declarado, e separa os elos por força para que quem lê veja a diferença.
    """
    rows = conn.query("SELECT * FROM result_chain($1)", project_id)
    strong = [r for r in rows if r["link_type"] in ("validated_causality", "observed_evidence")]
    weak = [r for r in rows if r["link_type"] in ("hypothesis", "inference", "association", "correlation")]
    return {
        "items": rows,
        "summary": {
            "links_total": len(rows),
            "with_evidence": sum(1 for r in rows if r["has_evidence"]),
            "externally_reviewed": sum(1 for r in rows if r["externally_reviewed"]),
            "strong_links": len(strong),
            "weak_links": len(weak),
        },
        # O aviso faz parte da resposta, não da interface: quem consome a API por conta própria também
        # precisa saber que hipótese não é evidência.
        "note": ("Elos marcados como hipótese, inferência, associação ou correlação NÃO são evidência "
                 "de causa. Apenas 'observed_evidence' e 'validated_causality' têm lastro, e a segunda "
                 "exige revisão por organização diferente da executora."),
    }


def territorial_gap(conn: Connection, *, territory_prefix: str | None = None) -> dict:
    """Demanda registrada contra oferta, por território — a pergunta "onde NÃO estamos investindo?".

    `needs_with_source` vem na resposta de propósito: território cuja demanda foi estimada sem citar
    fonte produz lacuna que não se deve tratar como fato, e a resposta diz isso em vez de esconder.
    """
    rows = conn.query("SELECT * FROM territorial_gap($1)", territory_prefix)
    out = []
    for r in rows:
        needs = int(r["needs_open"] or 0)
        offer = int(r["projects_published"] or 0) + int(r["programs_open"] or 0)
        sourced = int(r["needs_with_source"] or 0)
        out.append({
            **r,
            # Classificação explicada, nunca um número sozinho. Mesmo princípio do motor de prontidão.
            "gap": "sem_demanda_registrada" if needs == 0
                   else "demanda_sem_oferta" if offer == 0
                   else "demanda_acima_da_oferta" if needs > offer
                   else "oferta_compativel",
            "evidence_quality": "sem_fonte" if sourced == 0
                                else "parcial" if sourced < needs
                                else "com_fonte",
        })
    return {
        "items": out,
        "note": ("A lacuna compara necessidades REGISTRADAS na plataforma com projetos publicados e "
                 "programas abertos. Não é censo: território sem necessidade registrada aparece como "
                 "'sem_demanda_registrada', o que significa ausência de registro e não ausência de "
                 "demanda. `evidence_quality` diz quantas necessidades citam fonte."),
    }
