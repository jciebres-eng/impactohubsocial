"""Fan-out de notificação: um fato, toda a equipe avisada, uma vez só.

PEDIDO QUE ORIGINOU ESTE MÓDULO (verbatim): "trabalhar e implementar notificações para toda a equipe envolvida em cada
evolução ou modificação ou alteração de etapas do processo ou documentos juntados".

O que havia antes (RECONSTRUCTION_AUDIT.md §2.3): `notify_user` avisava UMA pessoa, `notify_counterpart` avisava a
contraparte de uma candidatura, `notify_once` tinha idempotência mas só servia cobrança. Nenhum deles sabia o que é
"a equipe de um projeto". Resultado prático: quando um documento era anexado, ninguém além de quem anexou sabia.

Aqui "equipe" é definida no banco (`project_team()`), não por lista escrita à mão, e inclui três grupos:
  1. quem é membro da organização dona do projeto;
  2. quem é membro de organização com relação de participação ATIVA no projeto (parceira, executora, apoiadora…);
  3. quem é membro de organização financiadora com candidatura aceita.
Isso significa que a equipe cresce sozinha quando uma relação nasce — sem recadastro.

Três garantias que valem para todo aviso daqui:
  * **Idempotência** — `dedupe_key` é único por pessoa. Reprocessar um webhook, repetir um PATCH ou rodar um job duas
    vezes não gera dois avisos. Sem isso, "avisar toda a equipe" viraria "irritar toda a equipe".
  * **Quem agiu não é avisado** — ninguém recebe notificação do seu próprio clique.
  * **Preferência respeitada** — `notification_prefs.in_app = false` silencia o grupo para aquela pessoa; o fato
    continua no `domain_events`, só o aviso não chega.

O retorno de cada função é o NÚMERO REAL de pessoas avisadas, e esse número é gravado no evento. Zero é resposta
legítima (equipe de uma pessoa que foi quem agiu) e fica visível em vez de ser maquiada.
"""
from __future__ import annotations

import hashlib
from typing import Any

from ..db.pq import Connection
from . import events

# Grupos de preferência. Precisam existir em `notification_prefs.grp`; ver CHECK da tabela.
GRP = {
    "relationship": "network", "proposal": "proposal", "listing": "network", "conversation": "message",
    "message": "message", "investment": "funding", "impact_update": "report", "experience": "network",
    "team": "project", "enforcement": "account", "project": "project", "document": "document",
    "diagnosis": "project", "milestone": "project", "indicator": "project", "risk": "project",
}

# Prioridade: muda ordenação e destaque na caixa, nunca o canal. `critical` é para o que trava o trabalho da
# pessoa — prazo vencendo, decisão pendente, medida de moderação.
#
# OS NOMES SÃO OS DO BANCO. Eu havia escrito `urgent` aqui enquanto o CHECK de `notifications.priority` diz
# `critical`: a divergência passava por lint, por type-check e por toda a suíte, e só apareceria na primeira
# notificação de prioridade máxima — que é o caminho da moderação. Há um teste de invariante que compara esta
# lista com o CHECK do banco, justamente para que não torne a divergir.
PRIORITIES = ("low", "normal", "high", "critical")


def dedupe(*parts: Any) -> str:
    """Chave estável e curta para o par (fato, referência). Mesmo fato ⇒ mesma chave ⇒ um aviso só."""
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


def _grp(event: str) -> str:
    return GRP.get(event.split(".", 1)[0].lower(), "network")


def team(conn: Connection, project_id: str) -> list[dict]:
    """Quem é a equipe deste projeto, com o motivo do vínculo. Serve à tela "quem será avisado"."""
    return conn.query(
        "SELECT t.user_id::text AS user_id, t.org_id::text AS org_id, t.relation,"
        " user_display_name(t.user_id) AS name, coalesce(o.trade_name, o.legal_name) AS org_name"
        " FROM project_team($1) t JOIN organizations o ON o.id = t.org_id"
        " ORDER BY CASE t.relation WHEN 'owner' THEN 0 WHEN 'participant' THEN 1 ELSE 2 END, t.user_id", project_id)


def project_event(conn: Connection, *, event: str, project_id: str, org_id: str, title: str, body: str | None = None,
                  link: str | None = None, actor_user_id: str | None = None, priority: str = "normal",
                  ref_type: str | None = None, ref_id: str | None = None, action_label: str | None = None,
                  payload: dict | None = None, dedupe_parts: tuple[Any, ...] | None = None) -> dict:
    """Grava o fato e avisa a equipe inteira do projeto. É a função que os motores chamam.

    `dedupe_parts` identifica o fato: por omissão, (evento, projeto, referência). Quando o mesmo evento pode repetir
    legitimamente — dois marcos concluídos no mesmo projeto — quem chama passa as partes que o tornam único.
    """
    if priority not in PRIORITIES:
        raise ValueError(f"prioridade inválida: {priority}")
    key = dedupe(*(dedupe_parts or (event, project_id, ref_type, ref_id)))
    sent = conn.scalar(
        "SELECT notify_team($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)", project_id, f"{_grp(event)}.{event.split('.')[-1]}",
        title[:200], (body or "")[:2000] or None, link, actor_user_id, priority, key, ref_type, ref_id, action_label)
    ev = events.record(conn, event=event, org_id=org_id, actor_user_id=actor_user_id, project_id=project_id,
                       subject_type=ref_type, subject_id=ref_id, payload=payload, notified=int(sent or 0))
    return {"event_id": ev, "notified": int(sent or 0), "dedupe_key": key}


def org_event(conn: Connection, *, event: str, org_id: str, title: str, body: str | None = None,
              link: str | None = None, actor_user_id: str | None = None, priority: str = "normal",
              ref_type: str | None = None, ref_id: str | None = None, min_role: str = "viewer",
              action_label: str | None = None, payload: dict | None = None, project_id: str | None = None,
              dedupe_parts: tuple[Any, ...] | None = None) -> dict:
    """Avisa a organização quando o fato não pertence a um projeto: proposta recebida, anúncio suspenso, medida aplicada.

    `min_role` existe porque nem todo fato é de todos: uma medida de moderação vai para admin/owner, não para quem só
    tem leitura. Decidir isso aqui evita que cada rota invente seu próprio critério.

    `action_label` é o que transforma o aviso em algo acionável — "Responder", "Analisar", "Ajustar". Sem ele, a
    pessoa lê que algo aconteceu e tem de descobrir sozinha o que fazer.
    """
    if priority not in PRIORITIES:
        raise ValueError(f"prioridade inválida: {priority}")
    key = dedupe(*(dedupe_parts or (event, org_id, ref_type, ref_id)))
    sent = conn.scalar(
        "SELECT notify_org_members($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)", org_id,
        f"{_grp(event)}.{event.split('.')[-1]}", title[:200], (body or "")[:2000] or None, link, actor_user_id,
        priority, key, ref_type, ref_id, min_role, action_label)
    ev = events.record(conn, event=event, org_id=org_id, actor_user_id=actor_user_id, project_id=project_id,
                       subject_type=ref_type, subject_id=ref_id, payload=payload, notified=int(sent or 0))
    return {"event_id": ev, "notified": int(sent or 0), "dedupe_key": key}


def fact_only(conn: Connection, *, event: str, org_id: str | None, actor_user_id: str | None = None,
              project_id: str | None = None, ref_type: str | None = None, ref_id: str | None = None,
              payload: dict | None = None) -> int:
    """Registra o fato SEM avisar ninguém.

    Existe para os fatos de alto volume (cada recado numa conversa) e para os que a pessoa avisada já está vendo
    acontecer. Gravar o fato ainda importa: a linha de tempo, a auditoria e as recomendações leem o evento, não a caixa
    de avisos.
    """
    return events.record(conn, event=event, org_id=org_id, actor_user_id=actor_user_id, project_id=project_id,
                         subject_type=ref_type, subject_id=ref_id, payload=payload, notified=0)
