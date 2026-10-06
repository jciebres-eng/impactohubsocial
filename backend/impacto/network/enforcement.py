"""Escada de moderação: medida proporcional, com regra, motivo e direito de contestar.

PEDIDO (§45-46): uma escada de dez degraus — orientação, advertência, notificação formal, restrição parcial,
suspensão temporária, bloqueio cautelar, desvinculação, cancelamento, banimento, encaminhamento — e, textualmente,
"nunca criar punição automática irreversível baseada somente em heurística".

Como isso virou estrutura, e não boa intenção:

* **Proporcionalidade com degrau.** Cada medida tem severidade declarada (1 a 10) e `escalation_ok()` recusa pular
  mais de dois degraus de uma vez sem haver medida anterior contra o mesmo alvo. Banimento como primeira resposta é
  recusado — tem de haver histórico, ou um fato grave citado explicitamente.
* **Regra e motivo obrigatórios** (`rule_ref`, `reason` ≥ 10 caracteres, CHECK no banco). Medida sem regra é
  arbítrio, e a plataforma não consegue registrar arbítrio.
* **Medida temporária exige prazo** (CHECK no banco). "Suspenso até nova ordem" não existe aqui.
* **Nada é automático.** Não há rota, trabalho ou gatilho que aplique medida por heurística: `apply()` exige
  `decided_by`, que vem de `app_uid()` de um administrador autenticado. O que a heurística faz é PRIORIZAR a fila
  (`reports.priority`), nunca decidir.
* **Quem julga a contestação não é quem aplicou** (CHECK no banco, `appeal_decided_by <> decided_by`).
* **A identidade de quem denunciou nunca chega ao alvo.** `reports.reporter_anonymous` é verdadeiro por padrão, e
  `target_view()` — a única leitura que o alvo tem — não seleciona a coluna do denunciante.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection
from ..http import ApiError, forbidden, not_found, unprocessable
from . import notify

#: A escada, em ordem. (medida, severidade, rótulo, exige prazo, o que ela faz na prática)
LADDER: tuple[tuple[str, int, str, bool, str], ...] = (
    ("guidance", 1, "Orientação", False,
     "Registro de orientação, sem restrição. Serve para dizer o que mudar antes de qualquer sanção."),
    ("warning", 2, "Advertência", False,
     "Advertência registrada. Fica no histórico e conta na proporcionalidade da próxima medida."),
    ("formal_notice", 3, "Notificação formal", False,
     "Notificação formal com prazo para correção, sem restringir o uso."),
    ("partial_restriction", 4, "Restrição parcial", True,
     "Restringe parte do uso (publicar, propor, enviar recado) mantendo o acesso aos próprios dados."),
    ("temporary_suspension", 6, "Suspensão temporária", True,
     "Suspende o uso por prazo determinado. Os dados continuam preservados e acessíveis à organização."),
    ("precautionary_freeze", 7, "Bloqueio cautelar", True,
     "Congela operações enquanto a apuração corre. É cautelar: não é juízo de mérito."),
    ("unlinking", 8, "Desvinculação", False,
     "Encerra relações ativas com terceiros, para proteger quem está do outro lado."),
    ("cancellation", 9, "Cancelamento", False,
     "Encerra a conta ou a organização na plataforma, preservando o que a lei exige preservar."),
    ("ban", 10, "Banimento", False,
     "Impede novo cadastro. Última medida, e nunca a primeira resposta a um fato isolado."),
    ("referral", 5, "Encaminhamento a autoridade", False,
     "Encaminha o caso à autoridade competente. Não é punição da plataforma: é dever de comunicar."),
)
MEASURES = tuple(m for m, *_ in LADDER)
SEVERITY = {m: s for m, s, *_ in LADDER}
LABEL = {m: lb for m, _, lb, _, _ in LADDER}
NEEDS_END = {m for m, _, _, needs, _ in LADDER if needs}
EFFECT = {m: eff for m, _, _, _, eff in LADDER}

#: As 12 categorias de denúncia do pedido.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("fraud", "Fraude ou falsidade"), ("abuse", "Abuso"), ("harassment", "Assédio"),
    ("hate_speech", "Discurso de ódio"), ("spam", "Spam ou abordagem em massa"),
    ("impersonation", "Falsa identidade"), ("misinformation", "Informação falsa"),
    ("privacy", "Violação de privacidade"), ("intellectual_property", "Propriedade intelectual"),
    ("illegal_content", "Conteúdo ilícito"), ("child_safety", "Risco a criança ou adolescente"),
    ("other", "Outro"),
)

STATUSES = ("active", "expired", "lifted", "under_appeal", "upheld", "overturned")

#: Quantos degraus de severidade se pode subir de uma vez sem histórico contra o mesmo alvo.
#: Dois é a folga que permite responder a algo sério sem transformar a escada em formalidade vazia — e sem permitir
#: que a primeira resposta a um fato isolado seja banimento.
MAX_JUMP = 2


def ladder() -> list[dict]:
    """A escada, para a interface mostrar o que cada degrau significa antes de alguém escolher."""
    return [{"measure": m, "severity": s, "label": lb, "requires_end_date": needs, "effect": eff}
            for m, s, lb, needs, eff in LADDER]


def history(conn: Connection, *, org_id: str | None = None, user_id: str | None = None) -> list[dict]:
    """Medidas anteriores contra o mesmo alvo. É o que torna a proporcionalidade verificável."""
    return conn.query(
        "SELECT id::text AS id, measure, severity, rule_ref, reason, status, starts_at, ends_at,"
        " appeal_at, appeal_decision, created_at FROM enforcement_actions"
        " WHERE ($1::uuid IS NOT NULL AND target_org_id = $1) OR ($2::uuid IS NOT NULL AND target_user_id = $2)"
        " ORDER BY created_at DESC", org_id, user_id)


def escalation_ok(measure: str, prior: list[dict]) -> tuple[bool, str]:
    """A medida é proporcional ao histórico?

    Sem medida anterior, o degrau máximo é `MAX_JUMP`. Com histórico, pode-se subir até dois degraus acima da
    severidade mais alta já aplicada. A conta é simples de propósito: uma regra que ninguém consegue repetir de
    cabeça não é aplicada de forma consistente.
    """
    want = SEVERITY[measure]
    top = max((int(p["severity"]) for p in prior if p["status"] not in ("overturned",)), default=0)
    if want <= max(MAX_JUMP, top + MAX_JUMP):
        return True, ""
    allowed = [m for m, s in SEVERITY.items() if s <= max(MAX_JUMP, top + MAX_JUMP)]
    return False, (
        f"Medida desproporcional ao histórico: severidade {want} com histórico máximo {top or 'nenhum'}. "
        f"Aplique primeiro uma medida de severidade até {max(MAX_JUMP, top + MAX_JUMP)} "
        f"({', '.join(LABEL[m] for m in allowed)}), ou registre a medida grave citando o fato que a justifica "
        f"em 'reason' e marcando 'override_reason'."
    )


def apply(conn: Connection, *, measure: str, decided_by: str, rule_ref: str, reason: str,
          target_org_id: str | None = None, target_user_id: str | None = None, report_id: str | None = None,
          evidence_note: str | None = None, ends_at: Any = None, override_reason: str | None = None) -> dict:
    """Aplica a medida. NUNCA chamada por trabalho automático: exige um administrador que decide e assina.

    `override_reason` é a válvula explícita para o caso grave que não cabe na escada — e ela não é silenciosa: fica
    gravada em `evidence_note` com o prefixo que a identifica, de modo que uma auditoria consiga listar todas as
    vezes em que a escada foi contornada e por quê.
    """
    if measure not in MEASURES:
        raise unprocessable(f"Medida desconhecida: {measure}", {"escada": [m for m, *_ in LADDER]})
    if (target_org_id is None) == (target_user_id is None):
        raise unprocessable("A medida tem um alvo: organização OU pessoa")
    if len(reason.strip()) < 10:
        raise unprocessable("Medida sem motivo é arbítrio: descreva em pelo menos 10 caracteres")
    if len(rule_ref.strip()) < 3:
        raise unprocessable("Informe a regra aplicada (rule_ref)")
    if measure in NEEDS_END and not ends_at:
        raise unprocessable(f"{LABEL[measure]} exige prazo de término")

    prior = history(conn, org_id=target_org_id, user_id=target_user_id)
    ok, why = escalation_ok(measure, prior)
    if not ok and not (override_reason and len(override_reason.strip()) >= 20):
        raise ApiError(409, "disproportionate", why,
                       {"historico": [{"measure": p["measure"], "severity": p["severity"]} for p in prior]})

    note = evidence_note
    if not ok:
        note = (f"[ESCADA CONTORNADA] {override_reason.strip()}"
                + (f"\n{evidence_note}" if evidence_note else ""))

    row = conn.one(
        "INSERT INTO enforcement_actions(target_org_id, target_user_id, report_id, measure, severity, rule_ref,"
        " reason, evidence_note, ends_at, decided_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)"
        " RETURNING id::text AS id, measure, severity, status, starts_at, ends_at",
        target_org_id, target_user_id, report_id, measure, SEVERITY[measure], rule_ref.strip(), reason.strip(),
        note, ends_at, decided_by)

    # O alvo é avisado da medida, com a regra e o prazo — e com o caminho para contestar. Aplicar sanção em silêncio
    # seria a pior forma de aplicá-la.
    if target_org_id:
        notify.org_event(
            conn, event="Enforcement.applied", org_id=target_org_id, actor_user_id=None,
            title=f"Medida aplicada: {LABEL[measure]}",
            body=f"{reason.strip()} Regra: {rule_ref.strip()}."
                 + (f" Vigora até {ends_at}." if ends_at else "")
                 + " Você pode contestar esta medida.",
            link="/conta/moderacao", priority="critical", ref_type="enforcement", ref_id=row["id"],
            min_role="admin", action_label="Contestar",
            payload={"measure": measure, "rule_ref": rule_ref.strip(), "escalation_override": not ok})
    return {**row, "label": LABEL[measure], "effect": EFFECT[measure], "escalation_override": not ok}


def lift(conn: Connection, *, action_id: str, decided_by: str, note: str) -> dict:
    """Levanta a medida. Exige motivo, como aplicar — desfazer também é decisão."""
    if len(note.strip()) < 3:
        raise unprocessable("Informe o motivo de levantar a medida")
    a = conn.one("SELECT status, measure, target_org_id::text AS target_org_id FROM enforcement_actions"
                 " WHERE id = $1", action_id)
    if not a:
        raise not_found("Medida")
    if a["status"] in ("lifted", "overturned", "expired"):
        raise ApiError(409, "already_closed", f"Medida já está como {a['status']}")
    conn.run("UPDATE enforcement_actions SET status = 'lifted', appeal_decision = $2, appeal_decided_by = $3,"
             " ends_at = coalesce(ends_at, now()) WHERE id = $1", action_id, note.strip(), decided_by)
    if a["target_org_id"]:
        notify.org_event(
            conn, event="Enforcement.applied", org_id=a["target_org_id"], actor_user_id=None,
            title=f"Medida levantada: {LABEL[a['measure']]}", body=note.strip(), link="/conta/moderacao",
            ref_type="enforcement", ref_id=action_id, min_role="admin",
            dedupe_parts=("Enforcement.lifted", action_id))
    return {"id": action_id, "status": "lifted"}


def appeal(conn: Connection, *, action_id: str, org_id: str | None, user_id: str | None, note: str) -> dict:
    """O ALVO contesta. É a única escrita que o alvo tem nesta tabela, e vale uma vez."""
    if len(note.strip()) < 10:
        raise unprocessable("Descreva a contestação em pelo menos 10 caracteres")
    a = conn.one("SELECT target_org_id::text AS target_org_id, target_user_id::text AS target_user_id, status,"
                 " appeal_at FROM enforcement_actions WHERE id = $1", action_id)
    if not a:
        raise not_found("Medida")
    if a["target_org_id"] != org_id and a["target_user_id"] != user_id:
        raise forbidden("Esta medida não é contra você")
    if a["appeal_at"]:
        raise ApiError(409, "already_appealed", "Esta medida já foi contestada")
    if a["status"] in ("lifted", "overturned"):
        raise ApiError(409, "already_closed", "Esta medida já foi desfeita")
    conn.run("UPDATE enforcement_actions SET appeal_note = $2, appeal_at = now(), status = 'under_appeal'"
             " WHERE id = $1", action_id, note.strip())
    return {"id": action_id, "status": "under_appeal"}


def decide_appeal(conn: Connection, *, action_id: str, decided_by: str, uphold: bool, note: str) -> dict:
    """Julga a contestação. O banco recusa se for a mesma pessoa que aplicou a medida."""
    if len(note.strip()) < 10:
        raise unprocessable("A decisão da contestação precisa ser fundamentada (mínimo 10 caracteres)")
    a = conn.one("SELECT status, measure, decided_by::text AS decided_by,"
                 " target_org_id::text AS target_org_id FROM enforcement_actions WHERE id = $1", action_id)
    if not a:
        raise not_found("Medida")
    if a["status"] != "under_appeal":
        raise ApiError(409, "not_under_appeal", "Não há contestação pendente nesta medida")
    if a["decided_by"] == decided_by:
        raise forbidden("Quem aplicou a medida não julga a contestação dela", "same_person")
    status = "upheld" if uphold else "overturned"
    conn.run("UPDATE enforcement_actions SET status = $2, appeal_decision = $3, appeal_decided_by = $4,"
             " ends_at = CASE WHEN $2 = 'overturned' THEN now() ELSE ends_at END WHERE id = $1",
             action_id, status, note.strip(), decided_by)
    if a["target_org_id"]:
        notify.org_event(
            conn, event="Enforcement.applied", org_id=a["target_org_id"], actor_user_id=None,
            title="Contestação " + ("mantida" if uphold else "acolhida"), body=note.strip(),
            link="/conta/moderacao", priority="high", ref_type="enforcement", ref_id=action_id,
            min_role="admin", dedupe_parts=("Enforcement.appeal", action_id, status))
    return {"id": action_id, "status": status}


def expire_due(conn: Connection, *, limit: int = 500) -> dict:
    """Encerra medidas temporárias vencidas. É o único caminho automático — e ele só AFROUXA, nunca aperta."""
    n = conn.run("UPDATE enforcement_actions SET status = 'expired'"
                 " WHERE status IN ('active','upheld') AND ends_at IS NOT NULL AND ends_at < now()")
    return {"expired": n,
            "note": "Trabalho automático só encerra medida vencida. Aplicar medida é sempre decisão de pessoa."}


def active_for(conn: Connection, *, org_id: str | None = None, user_id: str | None = None) -> list[dict]:
    """Medidas em vigor contra o alvo. Serve às telas e a quem precisa checar restrição."""
    return conn.query(
        "SELECT id::text AS id, measure, severity, rule_ref, reason, starts_at, ends_at, status"
        " FROM enforcement_actions WHERE status IN ('active','under_appeal','upheld')"
        "   AND (ends_at IS NULL OR ends_at > now())"
        "   AND (($1::uuid IS NOT NULL AND target_org_id = $1) OR ($2::uuid IS NOT NULL AND target_user_id = $2))"
        " ORDER BY severity DESC", org_id, user_id)


def target_view(conn: Connection, *, org_id: str | None = None, user_id: str | None = None) -> list[dict]:
    """O que o ALVO vê sobre as medidas contra si.

    Note o que esta consulta NÃO seleciona: nada que identifique quem denunciou. A identidade de quem denuncia não
    chega ao alvo — nem por este caminho, nem por nenhum outro, e `reports.reporter_anonymous` registra isso no
    próprio banco.
    """
    rows = conn.query(
        "SELECT id::text AS id, measure, severity, rule_ref, reason, evidence_note, starts_at, ends_at, status,"
        " appeal_note, appeal_at, appeal_decision, created_at FROM enforcement_actions"
        " WHERE (($1::uuid IS NOT NULL AND target_org_id = $1) OR ($2::uuid IS NOT NULL AND target_user_id = $2))"
        " ORDER BY created_at DESC", org_id, user_id)
    for r in rows:
        r["label"] = LABEL.get(r["measure"], r["measure"])
        r["effect"] = EFFECT.get(r["measure"])
        r["can_appeal"] = r["appeal_at"] is None and r["status"] not in ("lifted", "overturned", "expired")
    return rows
