"""v0.27.0 — "Para você hoje": cartões e contadores dinâmicos derivados de registros reais.

Um cartão é uma pendência, decisão ou avanço que a pessoa pode olhar em cinco segundos e, se quiser,
abrir. Nada aqui é novo estado: é a agregação do que já existe (pendências da Central, recomendações,
obrigações de acordo, participações a aceitar, repasses a confirmar, transferências a registrar,
reconhecimentos recebidos). Os contadores alimentam o menu (`badges`): a barra lateral mostra quantas
coisas esperam a pessoa em cada tela, lidas do servidor — a interface nunca conta por conta própria.

Regras:
  * cada cartão diz POR QUE existe (`why`) e PARA ONDE leva (`link`);
  * reconhecimentos aparecem como avanço cumulativo, nunca como "faltam X para o selo";
  * nenhum cartão vende nada: não há cartão de plano, assinatura ou upgrade.
"""
from __future__ import annotations

from ..db.pq import Connection

KIND_LABEL = {
    "operation_settled": "operações quitadas", "funding_settled": "aportes integralmente confirmados",
    "delivery_accepted": "entregas aceitas", "participation_paid": "participações de autoria pagas",
    "evidence_validated": "medições validadas",
}


def today(conn: Connection, *, user_id: str, org_id: str | None, org_kind: str | None) -> dict:
    from ..services import hub
    from ..trust import contract_rules, economy
    cards: list[dict] = []
    badges: dict[str, int] = {}

    # 1. pendências da Central (onboarding, compliance, documentos, concessão, chamados, eventos, cursos)
    try:
        pend = hub.pending_center(conn, user_id=user_id, org_id=org_id, org_kind=org_kind)
        for it in pend.get("items", [])[:6]:
            cards.append({"kind": it["kind"], "severity": it["severity"], "title": it["title"], "why": it.get("why"),
                          "link": it.get("link"), "source": "help.pending"})
    except Exception:  # noqa: BLE001 — a Central não pode derrubar a tela inicial; o cartão simplesmente não aparece
        pend = {"items": [], "onboarding_percent": None}

    if org_id:
        # 2. decisões de acordo (obrigações abertas, vencidas primeiro)
        obrig = contract_rules.pending_for(conn, org_id, limit=20)
        if obrig:
            badges["/acordos"] = len(obrig)
            for o in obrig[:3]:
                cards.append({"kind": "obligation", "severity": "high" if o["overdue"] else "medium",
                              "title": o["title"], "why": f"Acordo: {o['agreement_title']}" + (" · vencida" if o["overdue"] else ""),
                              "link": f"/acordos/{o['agreement_id']}", "due_on": o["due_on"], "source": "agreement_obligations"})
        # 3. participações de autoria que esperam o meu aceite (sou proponente)
        part = conn.query("SELECT id::text AS id, contribution FROM proponent_participations"
                          " WHERE proponent_org_id = $1 AND status IN ('proposed','under_review') ORDER BY created_at DESC LIMIT 5", org_id)
        if part:
            badges["/participacoes"] = len(part)
            cards.append({"kind": "participation", "severity": "medium",
                          "title": f"{len(part)} participação(ões) de autoria aguardam seu aceite",
                          "why": "Só vale com o seu aceite; nunca é automática.", "link": "/participacoes", "source": "proponent_participations"})
        # 4. repasses a confirmar (sou quem recebe) e transferências a registrar (sou quem paga)
        conf = conn.scalar("SELECT count(*) FROM payout_transfers t JOIN allocation_payouts p ON p.id = t.payout_id"
                           " WHERE p.recipient_org_id = $1 AND t.status = 'registered'", org_id) or 0
        if conf:
            badges["/acordos"] = badges.get("/acordos", 0) + int(conf)
            cards.append({"kind": "payout_confirm", "severity": "high", "title": f"{conf} transferência(s) registrada(s) esperam a sua confirmação",
                          "why": "Quem recebe confirma; nada vira pago por existir registro.", "link": "/acordos", "source": "payout_transfers"})
        pagar = conn.scalar("SELECT count(*) FROM allocation_payouts WHERE payer_org_id = $1 AND state = 'instruction_created'", org_id) or 0
        if pagar:
            badges["/acordos"] = badges.get("/acordos", 0) + int(pagar)
            cards.append({"kind": "payout_register", "severity": "medium", "title": f"{pagar} instrução(ões) de repasse sem transferência registrada",
                          "why": "O aporte é único e direcionado: registre cada transferência pela chave PIX do contrato.", "link": "/acordos", "source": "allocation_payouts"})
        # 5. recomendações abertas (próxima ação, com razão)
        try:
            from ..network import recommendation as RC
            recs = RC.listing(conn, org_id=org_id, status="open", limit=3)
            for r in recs:
                cards.append({"kind": "recommendation", "severity": "info", "title": r["title"], "why": r.get("rationale"),
                              "link": r.get("link"), "source": "recommendations"})
        except Exception:  # noqa: BLE001
            recs = []
        # 6. avanço cumulativo: reconhecimentos
        traj = economy.trajectory(conn, org_id)
        if traj["total"]:
            partes = [f"{v['count']} {KIND_LABEL.get(k, k)}" for k, v in traj["recognitions"].items()]
            cards.append({"kind": "trajectory", "severity": "info", "title": "Sua trajetória cresceu",
                          "why": " · ".join(partes), "link": "/perfil-publico", "source": "recognitions"})
    unread = conn.scalar("SELECT count(*) FROM notifications WHERE user_id = $1 AND read_at IS NULL", user_id) or 0
    if unread:
        badges["/notificacoes"] = int(unread)
    ordem = {"high": 0, "medium": 1, "info": 2}
    cards.sort(key=lambda c: ordem.get(c["severity"], 3))
    return {"cards": cards[:12], "badges": badges, "onboarding_percent": pend.get("onboarding_percent"),
            "trajectory": economy.trajectory(conn, org_id) if org_id else None,
            "note": "Cartões derivados de registros reais; nenhum vende plano ou assinatura. Reconhecimentos nascem de conclusão e quitação."}
