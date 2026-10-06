"""Monetização: a cadeia que separa valor criado de cobrança devida.

A cadeia que os documentos desta rodada exigem, e que é deliberadamente mais longa que
`valor → cobrança`:

    evento de valor → regra de elegibilidade → regra de monetização → VALIDAÇÃO JURÍDICA → cobrança

Cada seta é uma recusa possível, e as recusas estão no **banco**, não na disciplina de quem escreve a
rota. `monetization_rule_gate()` impede ativar uma regra que não tenha carta legal verde; e impede
**de todo** ativar `success_fee` e `marketplace_take_rate`, citando a ADR-022 pelo nome — a plataforma
não custodia nem processa aporte, logo não existe transação dela sobre a qual cobrar percentual.
Desfazer isso é decisão jurídica, não técnica.

A HIERARQUIA (ordem declarada nos documentos)

    1. SaaS institucional   ← núcleo
    2. B2G                  ← núcleo estratégico
    3. Enterprise / ESG     ← expansão
    4. Implementação        ← complementar
    5. Marketplace          ← upside, BLOQUEADO pela ADR-022
    6. Success fee          ← upside, BLOQUEADO pela ADR-022
    7. Premium do proponente ← aquisição, NUNCA núcleo
    8. Inteligência de dados ← expansão de alto valor

POR QUE NENHUM PREÇO INSTITUCIONAL ESTÁ FIXADO

Os documentos dão faixas e as qualificam: "Esses valores são hipóteses de posicionamento, não preços
finais." Então as faixas estão em `hypothesis_min_cents`/`hypothesis_max_cents` com a atribuição
escrita, e `amount_cents` é nulo. A plataforma já recusa contratar sem preço (`price_not_defined`), e
continua recusando — o que é o comportamento certo, não uma lacuna.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, IntegrityError, InsufficientPrivilege
from ..http import ApiError, forbidden, not_found, unprocessable

ENGINES = ("saas_institutional", "b2g", "enterprise", "implementation",
           "marketplace_take_rate", "success_fee", "proponent_premium", "data_intelligence")
ENGINE_LABEL = {
    "saas_institutional": "SaaS institucional", "b2g": "Governo (B2G)",
    "enterprise": "Enterprise / ESG", "implementation": "Implantação e integração",
    "marketplace_take_rate": "Marketplace (comissão)", "success_fee": "Taxa de êxito",
    "proponent_premium": "Premium de quem propõe", "data_intelligence": "Inteligência de dados",
}
#: Motores que a ADR-022 bloqueia por desenho, não por configuração.
BLOCKED_BY_ADR022 = ("success_fee", "marketplace_take_rate")
PRICING_MODES = ("included_in_plan", "unit", "subscription", "contract", "percentage")
LEGAL_STATUS = ("review_required", "validated", "refused")
CARD_STATUS = ("green", "yellow", "red")
BILLABLE_STATUS = ("candidate", "blocked_legal", "blocked_no_price", "eligible", "billed", "waived")
STATUS_LABEL = {
    "candidate": "candidato (regra desligada)", "blocked_legal": "bloqueado por revisão jurídica",
    "blocked_no_price": "bloqueado por falta de preço", "eligible": "elegível a cobrança",
    "billed": "cobrado", "waived": "incluído no plano",
}


def rules(conn: Connection, *, engine: str | None = None) -> dict:
    """As regras de receita, em ordem de hierarquia, com o estado real de cada uma.

    É leitura para quem tem conta, de propósito: quem paga tem direito de ver a regra que o cobra, o
    problema que ela diz resolver e se a carta legal está verde.
    """
    rows = conn.query(
        "SELECT r.key, r.label_pt, r.revenue_engine, r.engine_rank, r.payer_kind, r.trigger_kind,"
        " r.value_event_type, r.pricing_mode, r.amount_cents, r.percentage, r.currency,"
        " r.hypothesis_min_cents, r.hypothesis_max_cents, r.hypothesis_note, r.problem_solved,"
        " r.substitution_answer, r.legal_status, r.active, r.legal_card_id::text AS legal_card_id,"
        " c.status AS card_status, c.certainty AS card_certainty, c.needs_lawyer, c.needs_accountant,"
        " c.verified_on AS card_verified_on"
        " FROM monetization_rules r"
        " LEFT JOIN monetization_legal_cards c ON c.id = r.legal_card_id"
        " WHERE $1::text IS NULL OR r.revenue_engine = $1"
        " ORDER BY r.engine_rank, r.key", engine)
    out = []
    for r in rows:
        out.append({
            **r,
            "engine_label": ENGINE_LABEL.get(r["revenue_engine"], r["revenue_engine"]),
            "status_label": _rule_status(r),
            "blocked_by_adr022": r["revenue_engine"] in BLOCKED_BY_ADR022,
        })
    return {
        "items": out,
        "note": ("Nenhuma regra está ativa nesta versão. Preço institucional não foi fixado: as faixas "
                 "são hipóteses declaradas nos documentos da rodada, e sem preço definido a plataforma "
                 "recusa contratação online em vez de inventar. Taxa de êxito e comissão de "
                 "marketplace estão bloqueadas pela ADR-022 — a plataforma não custodia nem processa "
                 "aporte, logo não há transação dela sobre a qual cobrar percentual."),
    }


def _rule_status(r: dict) -> str:
    if r["active"]:
        return "ativa"
    if r["revenue_engine"] in BLOCKED_BY_ADR022:
        return "bloqueada pela ADR-022 (infraestrutura presente e desligada)"
    if r["legal_status"] != "validated":
        return "aguardando revisão jurídica"
    if r["pricing_mode"] in ("unit", "subscription") and r["amount_cents"] is None:
        return "aguardando definição de preço"
    return "pronta e desligada por decisão comercial"


def legal_cards(conn: Connection, *, rule_key: str | None = None) -> list[dict]:
    return conn.query(
        "SELECT id::text AS id, rule_key, payer, beneficiary, billing_event, revenue_nature,"
        " contractual_relation, required_document, required_terms, cancellation_policy, refund_policy,"
        " tax_notes, invoice_notes, regulatory_notes, legal_basis, source_name, source_url,"
        " verified_on, certainty, needs_lawyer, needs_accountant, open_questions, status, note,"
        " created_at FROM monetization_legal_cards"
        " WHERE $1::text IS NULL OR rule_key = $1 ORDER BY rule_key, created_at DESC", rule_key)


def add_legal_card(conn: Connection, *, actor: str | None, **f: Any) -> dict:
    """Registra a pesquisa de base normativa de uma receita.

    **Não é parecer jurídico.** `certainty` é o grau de certeza DA PESQUISA, e `needs_lawyer` nasce
    verdadeiro. Verde exige base, fonte, data, certeza alta e `needs_lawyer = false` — e o CHECK
    `green_needs_evidence` recusa marcar verde por ausência de proibição encontrada, que é a tentação
    óbvia e o erro que os documentos proíbem textualmente.
    """
    if not conn.one("SELECT 1 FROM monetization_rules WHERE key = $1", f.get("rule_key")):
        raise not_found("Regra de monetização")
    cols = ("rule_key", "payer", "beneficiary", "billing_event", "revenue_nature",
            "contractual_relation", "required_document", "required_terms", "cancellation_policy",
            "refund_policy", "tax_notes", "invoice_notes", "regulatory_notes", "legal_basis",
            "source_name", "source_url", "verified_on", "certainty", "needs_lawyer",
            "needs_accountant", "open_questions", "status", "note")
    names, args = [], []
    for c in cols:
        if c in f and f[c] is not None:
            names.append(c)
            args.append(f[c])
    names.append("created_by")
    args.append(actor)
    ph = ", ".join(f"${i + 1}" for i in range(len(args)))
    return conn.one(f"INSERT INTO monetization_legal_cards({', '.join(names)}) VALUES ({ph})"
                    " RETURNING id::text AS id, rule_key, status, certainty, created_at", *args)


def set_rule(conn: Connection, *, key: str, **f: Any) -> dict:
    """Ajusta uma regra: preço, moeda, situação jurídica, carta e ativação.

    Quem recusa de verdade é `monetization_rule_gate()` no banco. Esta função não repete a regra em
    Python de propósito — regra duplicada é regra que divergirá.
    """
    allowed = ("amount_cents", "percentage", "currency", "legal_status", "legal_card_id", "active",
               "hypothesis_min_cents", "hypothesis_max_cents", "hypothesis_note")
    sets, args = [], []
    for k in allowed:
        if k in f and f[k] is not None:
            args.append(f[k])
            sets.append(f"{k} = ${len(args)}")
    if not sets:
        raise unprocessable("Nada a alterar")
    args.append(key)
    # O portão é `monetization_rule_gate()` no banco. Mas a MENSAGEM dele importa — ela nomeia a
    # ADR-022, ou diz que falta carta legal, ou que falta preço — e o mapeamento padrão de
    # `InsufficientPrivilege` para 403 substitui a mensagem por um genérico "operação não permitida".
    # Então a exceção é capturada aqui só para PRESERVAR a explicação; a regra continua sendo uma só,
    # no banco.
    try:
        row = conn.one(f"UPDATE monetization_rules SET {', '.join(sets)} WHERE key = ${len(args)}"
                       " RETURNING key, amount_cents, currency, legal_status, active", *args)
    except (InsufficientPrivilege, IntegrityError) as exc:
        raise ApiError(422, "monetization_gate", _gate_message(exc)) from exc
    if not row:
        raise not_found("Regra de monetização")
    return row


def _gate_message(exc: Exception) -> str:
    """A primeira linha da mensagem do banco, que é a explicação da recusa."""
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return text[:500] or "A regra não pode ser ativada neste estado."


def pipeline(conn: Connection, *, org_id: str | None = None, status: str | None = None,
             limit: int = 50, offset: int = 0) -> dict:
    """A fila do que PODERIA ser cobrado, com o motivo de cada estado.

    É o número que torna a conversa comercial possível sem cobrar ninguém: "a plataforma criou N
    eventos de valor que uma regra alcança, e nenhum virou cobrança porque X".
    """
    rows = conn.query(
        "SELECT b.id, b.status, b.reason, b.amount_cents, b.currency, b.created_at,"
        " b.rule_key, r.label_pt AS rule_label, r.revenue_engine, v.event_type, v.units,"
        " v.org_id::text AS org_id"
        " FROM billable_events b"
        " JOIN monetization_rules r ON r.key = b.rule_key"
        " JOIN value_events v ON v.id = b.value_event_id"
        " WHERE ($1::uuid IS NULL OR b.org_id = $1) AND ($2::text IS NULL OR b.status = $2)"
        " ORDER BY b.id DESC LIMIT $3 OFFSET $4", org_id, status, limit + 1, offset)
    more = len(rows) > limit
    agg = conn.query(
        "SELECT status, count(*) AS n, sum(amount_cents) AS cents FROM billable_events"
        " WHERE $1::uuid IS NULL OR org_id = $1 GROUP BY status ORDER BY status", org_id)
    return {
        "items": [{**r, "status_label": STATUS_LABEL.get(r["status"], r["status"]),
                   "engine_label": ENGINE_LABEL.get(r["revenue_engine"], r["revenue_engine"])}
                  for r in rows[:limit]],
        "has_more": more, "limit": limit, "offset": offset,
        "by_status": [{**a, "status_label": STATUS_LABEL.get(a["status"], a["status"])} for a in agg],
        "note": ("Um evento de valor não produz cobrança: produz candidato. `reason` diz por que cada "
                 "um ainda não é cobrado — regra desligada, carta legal pendente, preço não definido "
                 "ou incluído no plano."),
    }


def waive(conn: Connection, *, billable_id: int, reason: str) -> dict:
    """Dispensa um candidato. Só a administração, e sempre com motivo escrito."""
    if len(reason or "") < 10:
        raise unprocessable("Dispensar exige motivo com ao menos 10 caracteres", {"campo": "reason"})
    row = conn.one("UPDATE billable_events SET status = 'waived', reason = $2 WHERE id = $1"
                   " AND status IN ('candidate','eligible','blocked_legal','blocked_no_price')"
                   " RETURNING id, status, reason", billable_id, reason)
    if not row:
        raise forbidden("Este candidato não pode ser dispensado neste estado", "cannot_waive")
    return row
