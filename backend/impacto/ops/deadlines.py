"""Varredura de prazos: avisar ANTES, não depois.

O QUE A AUDITORIA DA v0.20.0 ENCONTROU

A plataforma registrava cinco prazos diferentes e varria exatamente um. `documents.valid_until`
ganhava aviso em D-30/D-7/D-0 (`jobs.document_expiry`), e o resto vencia em silêncio:

* `milestones.due_on` — o marco do projeto, que é o compromisso que a organização assumiu;
* `calls.closes_at` — havia job, mas ele só FECHAVA a chamada; quem ia se candidatar descobria
  depois;
* `proposals.expires_at` — a função que expira existia e nunca era chamada (ver `jobs.proposal_expiry`);
* `seal_awards.expires_on` — `seal_status()` derivava `expired` depois da data, e ninguém era avisado
  antes. Um selo que cai sem aviso é a plataforma retirando em silêncio uma afirmação que fez;
* `signed_agreement_milestones.due_on` — o marco do instrumento assinado.

ESTE MÓDULO NÃO INVENTA PRAZO NENHUM. Ele lê as datas que as próprias organizações declararam e avisa
quem já tem direito de ver aquele objeto. Nenhuma data é estimada, nenhum prazo é atribuído a quem
não o declarou.

POR QUE D-30, D-7 E D-1

São as mesmas janelas que `jobs.document_expiry` já usava desde a v0.13.0. Repetir a janela
existente é melhor que inventar uma terceira cadência: a pessoa aprende um ritmo só. A chave de
deduplicação inclui a janela, então cada prazo rende no máximo três avisos — e reprocessar o job no
mesmo dia não rende nenhum a mais.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection
from ..network import notify

ENGINE_VERSION = "deadline-sweep@1.0.0"

# D-30, D-7 e D-1. A janela entra na chave de deduplicação: três avisos por prazo, no máximo.
WINDOWS = (30, 7, 1)


def _texto(dias: int) -> str:
    return "vence hoje" if dias <= 0 else ("vence amanhã" if dias == 1 else f"vence em {dias} dias")


def sweep(conn: Connection, *, limit: int = 500) -> dict[str, Any]:
    """Avisa os prazos que cruzaram D-30, D-7 ou D-1 hoje. Idempotente pela chave de deduplicação."""
    resultado = {"milestones": 0, "calls": 0, "proposals": 0, "seals": 0, "agreement_milestones": 0}

    # ---- marcos de projeto: avisa a EQUIPE, que é quem executa
    for m in conn.query(
            "SELECT m.id::text AS id, m.title, m.due_on, m.project_id::text AS project_id,"
            " p.org_id::text AS org_id, (m.due_on - current_date) AS dias"
            " FROM milestones m JOIN projects p ON p.id = m.project_id"
            " WHERE m.status NOT IN ('accepted','rejected') AND m.due_on IS NOT NULL"
            "   AND (m.due_on - current_date) = ANY($1::int[]) LIMIT $2", list(WINDOWS), limit):
        notify.project_event(
            conn, event="Milestone.due_soon", project_id=m["project_id"], org_id=m["org_id"],
            title=f"Marco {_texto(m['dias'])}: {m['title']}",
            body=f"Prazo declarado para {m['due_on']}.", link=f"/projetos/{m['project_id']}",
            priority="high" if m["dias"] <= 7 else "normal", ref_type="milestone", ref_id=m["id"],
            action_label="Abrir marco", payload={"due_on": str(m["due_on"]), "window": m["dias"]},
            dedupe_parts=("Milestone.due_soon", m["id"], m["dias"]))
        resultado["milestones"] += 1

    # ---- selos a vencer: a plataforma avisa ANTES de retirar o que ela própria afirmou
    for s in conn.query(
            "SELECT a.id::text AS id, a.org_id::text AS org_id, d.title,"
            " a.expires_on, (a.expires_on - current_date) AS dias"
            " FROM seal_awards a JOIN seal_definitions d ON d.id = a.definition_id"
            " CROSS JOIN LATERAL seal_status(a.id) st"
            " WHERE st.status = 'active' AND a.expires_on IS NOT NULL"
            "   AND (a.expires_on - current_date) = ANY($1::int[]) LIMIT $2", list(WINDOWS), limit):
        notify.org_event(
            conn, event="Seal.expiring", org_id=s["org_id"],
            title=f"Selo {_texto(s['dias'])}: {s['title']}",
            body=("Quando o prazo passar, o selo deixa de ser exibido. Renovar exige satisfazer de "
                  "novo os critérios — a plataforma não prorroga selo por tempo de casa."),
            link="/organizacao/selos", priority="high", min_role="admin",
            ref_type="seal_award", ref_id=s["id"], action_label="Ver critérios",
            payload={"expires_on": str(s["expires_on"]), "window": s["dias"]},
            dedupe_parts=("Seal.expiring", s["id"], s["dias"]))
        resultado["seals"] += 1

    # ---- propostas a vencer: avisa QUEM RECEBEU, que é quem perde a chance de responder
    for p in conn.query(
            "SELECT id::text AS id, title, receiver_org_id::text AS org_id, expires_at,"
            " (expires_at::date - current_date) AS dias FROM proposals"
            " WHERE status IN ('sent','viewed','in_review','changes_requested')"
            "   AND expires_at IS NOT NULL AND (expires_at::date - current_date) = ANY($1::int[])"
            " LIMIT $2", list(WINDOWS), limit):
        notify.org_event(
            conn, event="Proposal.expiring", org_id=p["org_id"],
            title=f"Proposta {_texto(p['dias'])}: {p['title']}",
            body="Sem resposta até o prazo, a proposta expira sozinha.",
            link=f"/propostas/{p['id']}", priority="high", min_role="member",
            ref_type="proposal", ref_id=p["id"], action_label="Responder",
            payload={"expires_at": str(p["expires_at"]), "window": p["dias"]},
            dedupe_parts=("Proposal.expiring", p["id"], p["dias"]))
        resultado["proposals"] += 1

    # ---- marcos de instrumento assinado
    for a in conn.query(
            "SELECT m.id::text AS id, m.title, m.due_on, m.org_id::text AS org_id,"
            " (m.due_on - current_date) AS dias FROM signed_agreement_milestones m"
            " JOIN signed_agreements g ON g.id = m.agreement_id"
            " WHERE g.status = 'active' AND m.status NOT IN ('accepted','canceled','rejected')"
            "   AND m.due_on IS NOT NULL"
            "   AND (m.due_on - current_date) = ANY($1::int[]) LIMIT $2", list(WINDOWS), limit):
        notify.org_event(
            conn, event="Agreement.milestone_due", org_id=a["org_id"],
            title=f"Marco do instrumento {_texto(a['dias'])}: {a['title']}",
            body=f"Prazo declarado para {a['due_on']}.", link="/instrumentos",
            priority="high", min_role="manager", ref_type="agreement_milestone", ref_id=a["id"],
            action_label="Abrir instrumento",
            payload={"due_on": str(a["due_on"]), "window": a["dias"]},
            dedupe_parts=("Agreement.milestone_due", a["id"], a["dias"]))
        resultado["agreement_milestones"] += 1

    # ---- chamadas a fechar: quem tem candidatura em rascunho precisa saber ANTES do fechamento
    for ch in conn.query(
            "SELECT DISTINCT c.id::text AS id, c.title, c.closes_at,"
            " a.osc_org_id::text AS org_id, (c.closes_at::date - current_date) AS dias FROM calls c"
            " JOIN applications a ON a.call_id = c.id AND a.status IN ('draft','submitted')"
            " WHERE c.status = 'open' AND c.closes_at IS NOT NULL"
            "   AND (c.closes_at::date - current_date) = ANY($1::int[]) LIMIT $2",
            list(WINDOWS), limit):
        notify.org_event(
            conn, event="Call.closing", org_id=ch["org_id"],
            title=f"Chamada {_texto(ch['dias'])}: {ch['title']}",
            body="Depois do fechamento a candidatura não pode mais ser enviada nem alterada.",
            link=f"/chamadas/{ch['id']}", priority="high", min_role="member",
            ref_type="call", ref_id=ch["id"], action_label="Abrir candidatura",
            payload={"closes_at": str(ch["closes_at"]), "window": ch["dias"]},
            dedupe_parts=("Call.closing", ch["id"], ch["org_id"], ch["dias"]))
        resultado["calls"] += 1

    resultado["note"] = (
        "Avisos emitidos em D-30, D-7 e D-1 sobre prazos DECLARADOS pelas próprias organizações. "
        "Nenhuma data foi estimada pela plataforma.")
    return resultado
