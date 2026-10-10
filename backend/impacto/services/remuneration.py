"""Obrigações de remuneração da plataforma e a política "gratuito até gerar valor" — v0.34.0 (ADR-377 a ADR-381).

A REGRA (NON_CUSTODIAL_ARCHITECTURE.md §0 continua acima de tudo): a plataforma calcula, comunica, fatura e concilia a
sua remuneração; nunca a desconta de dinheiro que não é dela, nunca retém repasse, nunca condiciona prestação de contas.

CADEIA DE ESTADOS (uma obrigação por fato gerador × regra; valor congelado na criação):
  calculated → (exempt) → due → invoiced → charged → received → settled
  desvios: reversed (base estornada antes de receber), overdue (vencida), disputed (contestação), waived (dispensa)

GATILHO AUDITÁVEL para `due` (free_until_value):
  1. a regra do catálogo está ATIVA (`monetization_rules.active`) — hoje nenhuma está;
  2. a origem do recurso não é pública sem autorização por instrumento (ADR-379);
  3. a organização passou da FRANQUIA de valor LIQUIDADO (não confirmado: liquidado) nos últimos 12 meses;
  4. existe aviso prévio `charging_starts` enviado há pelo menos `notice_days`;
  5. o total devido no período não ultrapassa `max_fee_share_of_settled_bps` do liquidado.
Se qualquer condição falhar, a obrigação fica `calculated` (ou `exempt`) com o motivo registrado — e NADA é devido.

O que este módulo NÃO faz: não cria cobrança real (a fatura é `platform_charges` kind 'operation', provedor manual/sandbox);
não bloqueia nada (ADR-381: nenhuma rota de prestação de contas consulta este módulo — `test_v0340_remuneration` varre).
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ..db.pq import Connection
from ..http import ApiError, not_found, unprocessable
from .donations import apply_bps

POLICY_KEY = "free_until_value"
NOTICE_TEXTS = {
    "free_until_value_intro": (
        "Gratuito até gerar valor: a plataforma calcula e mostra a sua taxa de serviço em cada doação confirmada, mas nada é "
        "devido enquanto (1) a regra comercial não estiver ativa, (2) o valor LIQUIDADO ao seu favor nos últimos 12 meses não "
        "passar da franquia da política vigente e (3) você não tiver sido avisado com antecedência. Prestação de contas, "
        "exportações e página pública nunca dependem de pagamento."),
    "allowance_approaching": (
        "Aviso: o valor liquidado ao seu favor nos últimos 12 meses está perto da franquia da política 'gratuito até gerar "
        "valor'. Passando a franquia, e só depois de um aviso formal com prazo, a taxa de serviço calculada passa a ser devida."),
    "charging_starts": (
        "Aviso formal: a partir da data deste aviso e respeitado o prazo mínimo, as taxas de serviço calculadas sobre doações "
        "LIQUIDADAS acima da franquia passam a ser devidas e serão faturadas à parte. Nada é descontado das doações. "
        "Sua prestação de contas, exportações e página pública continuam disponíveis independentemente de pagamento."),
    "invoice_issued": "Fatura emitida pela taxa de serviço devida, com o cálculo e a versão da regra anexados.",
    "overdue": "Fatura vencida. Nenhum acesso é bloqueado; você pode contestar pela própria plataforma.",
    "dispute_received": "Contestação recebida: a obrigação fica em disputa até decisão registrada.",
    "waived": "Obrigação dispensada por decisão registrada.",
}


# ============================================================================ política
def policy(c: Connection) -> dict:
    row = c.one("SELECT id, version, content, legal_status FROM monetization_policy_versions WHERE key = $1"
                " AND effective_from <= now() AND (effective_to IS NULL OR effective_to > now()) ORDER BY version DESC LIMIT 1", POLICY_KEY)
    if not row:
        raise ApiError(500, "policy_missing", "política free_until_value ausente")
    content = row["content"] if isinstance(row["content"], dict) else json.loads(row["content"])
    return {"id": int(row["id"]), "version": int(row["version"]), "legal_status": row["legal_status"], **content}


def rule_active(c: Connection, rule_key: str) -> bool:
    return bool(c.scalar("SELECT active FROM monetization_rules WHERE key = $1", rule_key))


def settled_volume_12m(c: Connection, org_id: str) -> int:
    """Soma LIQUIDADA (não confirmada) ao favor da organização nos últimos 12 meses, descontados estornos."""
    v = c.scalar("SELECT coalesce(sum(amount_cents + cover_costs_cents - refunded_cents), 0) FROM donations"
                 " WHERE beneficiary_org_id = $1 AND settled_at IS NOT NULL AND settled_at > now() - interval '12 months'"
                 " AND status IN ('confirmed','reconciled','partially_refunded')", org_id)
    return int(v or 0)


# ============================================================================ registro
def register(c: Connection, *, org_id: str, source_kind: str, source_id: str, rule_key: str, rule_version_id: int | None,
             basis_cents: int, amount_cents: int, funding_source: str = "private", campaign_id: str | None = None,
             public_instrument_ref: str | None = None) -> dict:
    """Registra a obrigação CALCULADA (idempotente por fato × regra). Recurso público nasce `exempt` (ADR-379)."""
    existing = c.one("SELECT id::text AS id, state FROM remuneration_obligations WHERE source_kind = $1 AND source_id = $2 AND rule_key = $3",
                     source_kind, source_id, rule_key)
    if existing:
        return existing | {"duplicate": True}
    pol = policy(c)
    state = "exempt" if funding_source in ("public", "mixed") and pol.get("public_funding_default", "exempt") == "exempt" else "calculated"
    if amount_cents == 0:
        state = "exempt"
    oid = c.scalar(
        "INSERT INTO remuneration_obligations(org_id, source_kind, source_id, campaign_id, rule_key, rule_version_id, basis_cents, amount_cents,"
        " funding_source, public_instrument_ref, state, policy_version_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING id::text",
        org_id, source_kind, source_id, campaign_id, rule_key, rule_version_id, basis_cents, amount_cents, funding_source,
        public_instrument_ref, state, pol["id"])
    return {"id": oid, "state": state, "duplicate": False}


def _get(c: Connection, obligation_id: str) -> dict:
    o = c.one("SELECT o.*, o.id::text AS id, o.org_id::text AS org_id, o.campaign_id::text AS campaign_id FROM remuneration_obligations o WHERE o.id = $1", obligation_id)
    if not o:
        raise not_found("Obrigação")
    return o


def _set(c: Connection, obligation_id: str, state: str, *, actor: str | None = None, **cols: Any) -> None:
    sets = ["state = $2", "decided_by = $3"]
    args: list[Any] = [obligation_id, state, actor]
    for k, v in cols.items():
        args.append(v)
        sets.append(f"{k} = ${len(args)}")
    c.run(f"UPDATE remuneration_obligations SET {', '.join(sets)} WHERE id = $1", *args)


# ============================================================================ avisos
def send_notice(c: Connection, *, org_id: str, kind: str, rule_key: str | None = None, created_by: str | None = None,
                body: str | None = None, channel: str = "in_app") -> str:
    if kind not in NOTICE_TEXTS:
        raise unprocessable("tipo de aviso desconhecido", code="notice_kind")
    pol = policy(c)
    text = body or NOTICE_TEXTS[kind]
    return c.scalar("INSERT INTO remuneration_notices(org_id, kind, policy_version_id, rule_key, body, channel, created_by)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id::text", org_id, kind, pol["id"], rule_key, text, channel, created_by)


def latest_notice(c: Connection, org_id: str, kind: str) -> dict | None:
    return c.one("SELECT id::text AS id, sent_at, acknowledged_at, policy_version_id FROM remuneration_notices WHERE org_id = $1 AND kind = $2"
                 " ORDER BY sent_at DESC LIMIT 1", org_id, kind)


# ============================================================================ gatilho auditável
def evaluate(c: Connection, *, org_id: str, actor: str | None = None, today: date | None = None) -> dict:
    """Aplica a política à organização: devolve, para cada obrigação `calculated`, por que (não) ficou devida.

    Nunca cria cobrança; nunca bloqueia. Só muda `calculated → due` quando as cinco condições valem."""
    pol = policy(c)
    today = today or datetime.now(UTC).date()
    settled = settled_volume_12m(c, org_id)
    allowance = int(pol.get("allowance_settled_cents_12m", 0))
    rows = c.query("SELECT id::text AS id, rule_key, amount_cents, funding_source, public_fee_authorized, state"
                   " FROM remuneration_obligations WHERE org_id = $1 AND state IN ('calculated','exempt') ORDER BY created_at", org_id)
    notice = latest_notice(c, org_id, "charging_starts")
    notice_ok = bool(notice and notice["sent_at"] <= datetime.now(UTC) - timedelta(days=int(pol.get("notice_days", 30))))
    due_now = int(c.scalar("SELECT coalesce(sum(amount_cents),0) FROM remuneration_obligations WHERE org_id = $1"
                           " AND state IN ('due','invoiced','charged','overdue') AND created_at > now() - interval '12 months'", org_id) or 0)
    cap = apply_bps(settled, int(pol.get("max_fee_share_of_settled_bps", 500)))
    out = {"org_id": org_id, "policy_version": pol["version"], "settled_12m_cents": settled, "allowance_cents": allowance,
           "notice": notice, "became_due": [], "kept": []}
    for r in rows:
        reasons = []
        if not rule_active(c, r["rule_key"]):
            reasons.append("rule_inactive")
        if r["funding_source"] in ("public", "mixed") and not r["public_fee_authorized"]:
            reasons.append("public_funding_exempt")
        if settled <= allowance:
            reasons.append("within_allowance")
        if not notice_ok:
            reasons.append("notice_pending" if not notice else "notice_period_running")
        if due_now + int(r["amount_cents"]) > cap:
            reasons.append("fee_share_cap")
        if reasons:
            out["kept"].append({"id": r["id"], "state": r["state"], "reasons": reasons})
            continue
        trigger = "settled_above_allowance_after_notice"
        _set(c, r["id"], "due", actor=actor, trigger_code=trigger, trigger_at=datetime.now(UTC), notice_id=notice["id"],
             due_on=today + timedelta(days=int(pol.get("due_days_after_invoice", 30))), policy_version_id=pol["id"])
        due_now += int(r["amount_cents"])
        out["became_due"].append({"id": r["id"], "trigger": trigger})
    return out


# ============================================================================ faturar, cobrar, receber, liquidar
def invoice(c: Connection, *, obligation_ids: list[str], actor: str, provider: str = "manual") -> dict:
    """Agrupa obrigações DEVIDAS de uma organização numa cobrança própria (`platform_charges` kind 'operation').
    Nada é descontado de doação. Abaixo do mínimo da política, acumula e não fatura."""
    pol = policy(c)
    rows = [_get(c, i) for i in obligation_ids]
    if not rows:
        raise unprocessable("nenhuma obrigação informada", code="empty")
    org = rows[0]["org_id"]
    if any(r["org_id"] != org for r in rows):
        raise unprocessable("obrigações de organizações diferentes não entram na mesma fatura", code="mixed_orgs")
    if any(r["state"] != "due" for r in rows):
        raise unprocessable("só obrigação DEVIDA é faturada", code="obligation_state")
    total = sum(int(r["amount_cents"]) for r in rows)
    if total < int(pol.get("min_invoice_cents", 0)):
        raise unprocessable(f"abaixo do mínimo de fatura da política ({pol.get('min_invoice_cents')} centavos): acumula", code="below_minimum")
    due_on = datetime.now(UTC).date() + timedelta(days=int(pol.get("due_days_after_invoice", 30)))
    cid = c.scalar("INSERT INTO platform_charges(org_id, kind, method, amount_cents, currency, state, provider, due_on, created_by)"
                   " VALUES ($1,'operation','manual',$2,'BRL','created',$3,$4,$5) RETURNING id::text", org, total, provider, due_on, actor)
    nid = send_notice(c, org_id=org, kind="invoice_issued", created_by=actor,
                      body=f"Fatura emitida: {len(rows)} obrigação(ões), total {total} centavos, vencimento {due_on.isoformat()}. "
                           "Cálculo e versão da regra constam de cada obrigação. Nenhum acesso é condicionado ao pagamento.")
    for r in rows:
        _set(c, r["id"], "invoiced", actor=actor, platform_charge_id=cid, notice_id=nid, due_on=due_on)
    return {"platform_charge_id": cid, "total_cents": total, "due_on": due_on.isoformat(), "obligations": [r["id"] for r in rows]}


def mark_charged(c: Connection, *, obligation_id: str, actor: str) -> dict:
    o = _get(c, obligation_id)
    if o["state"] != "invoiced":
        raise unprocessable("só obrigação faturada é marcada como cobrada", code="obligation_state")
    _set(c, obligation_id, "charged", actor=actor)
    return {"state": "charged"}


def register_receipt(c: Connection, *, obligation_id: str, actor: str, received_cents: int, reference: str) -> dict:
    """Pagamento RECEBIDO pela plataforma, com referência (comprovante/E2E). Parcial fica registrado; total muda o estado."""
    o = _get(c, obligation_id)
    if o["state"] not in ("invoiced", "charged", "overdue", "disputed"):
        raise unprocessable("recebimento exige obrigação faturada/cobrada/vencida/em disputa", code="obligation_state")
    if received_cents <= 0:
        raise unprocessable("valor recebido deve ser positivo", code="amount")
    total = int(o["received_cents"]) + int(received_cents)
    if total > int(o["amount_cents"]):
        raise unprocessable("recebido maior que o devido: registrar diferença como ajuste, não aqui", code="over_receipt")
    if total == int(o["amount_cents"]):
        _set(c, obligation_id, "received", actor=actor, received_cents=total, received_reference=reference[:120], received_at=datetime.now(UTC))
        return {"state": "received", "received_cents": total}
    c.run("UPDATE remuneration_obligations SET received_cents = $2, received_reference = $3 WHERE id = $1", obligation_id, total, reference[:120])
    return {"state": o["state"], "received_cents": total, "partial": True}


def _four_eyes(c: Connection, obligation_id: str, actor: str, handled: tuple[str, ...]) -> None:
    """v0.35.0 (auditoria, AUTHZ-06): quem operou a cobrança (faturou, cobrou, registrou o recebimento) não decide sozinho o
    desfecho dela (liquidar, reembolsar, dispensar, decidir disputa) — antes, uma pessoa com finance.approve fazia tudo."""
    if actor and c.scalar("SELECT 1 FROM remuneration_obligation_events WHERE obligation_id = $1 AND actor_id = $2"
                          " AND to_state = ANY($3::text[]) LIMIT 1", obligation_id, actor, list(handled)):
        from ..http import ApiError
        raise ApiError(403, "four_eyes", "Quem operou esta cobrança não pode decidir o desfecho dela: é preciso outra pessoa")


def mark_settled(c: Connection, *, obligation_id: str, actor: str, note: str) -> dict:
    o = _get(c, obligation_id)
    if o["state"] != "received":
        raise unprocessable("liquidação exige obrigação recebida", code="obligation_state")
    _four_eyes(c, obligation_id, actor, ("received",))
    _set(c, obligation_id, "settled", actor=actor, settled_at=datetime.now(UTC), received_reference=(o["received_reference"] or "") )
    c.run("INSERT INTO remuneration_obligation_events(obligation_id, from_state, to_state, actor_id, note) VALUES ($1,'settled','settled',$2,$3)",
          obligation_id, actor, "conciliação: " + note[:1900])
    return {"state": "settled"}


def mark_overdue(c: Connection, *, today: date | None = None) -> int:
    pol = policy(c)
    today = today or datetime.now(UTC).date()
    limit = today - timedelta(days=int(pol.get("overdue_grace_days", 0)))
    rows = c.query("SELECT id::text AS id, org_id::text AS org_id FROM remuneration_obligations WHERE state IN ('invoiced','charged') AND due_on < $1", limit)
    for r in rows:
        _set(c, r["id"], "overdue")
        send_notice(c, org_id=r["org_id"], kind="overdue")
    return len(rows)


def dispute(c: Connection, *, obligation_id: str, org_id: str, actor: str, reason: str) -> dict:
    o = _get(c, obligation_id)
    if o["org_id"] != org_id:
        raise not_found("Obrigação")
    if o["state"] not in ("due", "invoiced", "charged", "overdue", "received", "settled"):
        raise unprocessable("nada a contestar neste estado", code="obligation_state")
    if len(reason or "") < 10:
        raise unprocessable("contestação exige justificativa", code="reason_required")
    _set(c, obligation_id, "disputed", actor=actor, dispute_reason=reason[:2000])
    send_notice(c, org_id=org_id, kind="dispute_received", created_by=actor)
    return {"state": "disputed"}


def decide_dispute(c: Connection, *, obligation_id: str, actor: str, outcome: str, note: str) -> dict:
    o = _get(c, obligation_id)
    if o["state"] != "disputed":
        raise unprocessable("obrigação não está em disputa", code="obligation_state")
    if len(note or "") < 10:
        raise unprocessable("decisão exige justificativa", code="reason_required")
    _four_eyes(c, obligation_id, actor, ("invoiced", "charged", "received"))
    if outcome == "uphold":
        target = "invoiced" if o["platform_charge_id"] else "due"
        _set(c, obligation_id, target, actor=actor)
    elif outcome == "waive":
        _set(c, obligation_id, "waived", actor=actor, waived_reason=note[:2000])
        send_notice(c, org_id=o["org_id"], kind="waived", created_by=actor)
    elif outcome == "exempt":
        _set(c, obligation_id, "exempt", actor=actor)
    else:
        raise unprocessable("decisão desconhecida", code="outcome")
    c.run("INSERT INTO remuneration_obligation_events(obligation_id, from_state, to_state, actor_id, note) VALUES ($1,'disputed',$2,$3,$4)",
          obligation_id, "decision:" + outcome, actor, note[:2000])
    return {"state": c.scalar("SELECT state FROM remuneration_obligations WHERE id = $1", obligation_id)}


def waive(c: Connection, *, obligation_id: str, actor: str, reason: str) -> dict:
    o = _get(c, obligation_id)
    if o["state"] in ("received", "settled", "reversed", "waived"):
        raise unprocessable("não se dispensa obrigação recebida/liquidada/estornada", code="obligation_state")
    if len(reason or "") < 10:
        raise unprocessable("dispensa exige justificativa", code="reason_required")
    _four_eyes(c, obligation_id, actor, ("invoiced", "charged", "received"))
    _set(c, obligation_id, "waived", actor=actor, waived_reason=reason[:2000])
    send_notice(c, org_id=o["org_id"], kind="waived", created_by=actor)
    return {"state": "waived"}


def authorize_public_fee(c: Connection, *, obligation_id: str, actor: str, instrument_ref: str, note: str) -> dict:
    """Recurso público só vira elegível com instrumento identificado e autorização registrada (ADR-379)."""
    o = _get(c, obligation_id)
    if o["funding_source"] not in ("public", "mixed"):
        raise unprocessable("obrigação não é de recurso público", code="not_public")
    if len(instrument_ref or "") < 5 or len(note or "") < 10:
        raise unprocessable("autorização exige instrumento e justificativa", code="reason_required")
    c.run("UPDATE remuneration_obligations SET public_fee_authorized = true, public_instrument_ref = $2, public_fee_authorization_note = $3, decided_by = $4 WHERE id = $1",
          obligation_id, instrument_ref[:300], note[:2000], actor)
    if o["state"] == "exempt":
        _set(c, obligation_id, "calculated", actor=actor)
    return {"state": c.scalar("SELECT state FROM remuneration_obligations WHERE id = $1", obligation_id), "public_fee_authorized": True}


def register_donor_contribution(c: Connection, *, org_id: str, donation_id: str, campaign_id: str, amount_cents: int,
                                split_received_cents: int = 0, reference: str | None = None) -> dict:
    """Contribuição VOLUNTÁRIA do doador à plataforma (ADR-384). Não é taxa sobre a organização: o doador escolheu e pagou
    a mais. Por isso nasce DEVIDA (gatilho `donor_opt_in_contribution`) sem passar pela franquia de "gratuito até gerar
    valor". Se o provedor confirmou o split no próprio evento, nasce RECEBIDA com a referência do evento; senão, a
    organização que recebeu o valor deve repassá-lo (fatura própria, nunca desconto de doação)."""
    reg = register(c, org_id=org_id, source_kind="donation", source_id=donation_id, rule_key="donation.platform_contribution",
                   rule_version_id=None, basis_cents=amount_cents, amount_cents=amount_cents, funding_source="private", campaign_id=campaign_id)
    if reg.get("duplicate"):
        return reg
    pol = policy(c)
    _set(c, reg["id"], "due", trigger_code="donor_opt_in_contribution", trigger_at=datetime.now(UTC),
         due_on=datetime.now(UTC).date() + timedelta(days=int(pol.get("due_days_after_invoice", 30))))
    if split_received_cents and split_received_cents == amount_cents:
        _set(c, reg["id"], "received", received_cents=amount_cents, received_reference=(reference or "split")[:120], received_at=datetime.now(UTC))
        return {"id": reg["id"], "state": "received", "via": "split"}
    return {"id": reg["id"], "state": "due", "via": "invoice"}


def on_platform_charge_refunded(c: Connection, *, platform_charge_id: str, full: bool, refunded_cents: int) -> list[str]:
    """Reembolso da COBRANÇA da plataforma (cenário 39): o que a plataforma cobrou e devolveu deixa de ser receita.
    Total → obrigações da cobrança viram `reversed` (com evento no histórico). Parcial → fica registrado, sem mudar estado:
    a diferença é ajuste decidido por pessoa, nunca automático."""
    rows = c.query("SELECT id::text AS id, state FROM remuneration_obligations WHERE platform_charge_id = $1", platform_charge_id)
    out = []
    for r in rows:
        if full and r["state"] in ("invoiced", "charged", "overdue", "received", "settled", "disputed"):
            _set(c, r["id"], "reversed")
            out.append(r["id"])
        c.run("INSERT INTO remuneration_obligation_events(obligation_id, from_state, to_state, note) VALUES ($1,$2,$3,$4)",
              r["id"], r["state"], "reversed" if (full and r["id"] in out) else r["state"],
              (f"cobrança da plataforma reembolsada ({refunded_cents} centavos)" + ("" if full else " — parcial: ajuste por decisão humana"))[:2000])
    return out


def refund_received(c: Connection, *, obligation_id: str, actor: str, refunded_cents: int, reference: str, note: str) -> dict:
    """A plataforma DEVOLVE o que recebeu (ex.: reembolso de serviço cancelado, cobrança indevida). Só integral: parcial é
    ajuste com decisão própria. A obrigação vira `reversed`; o histórico guarda referência e motivo."""
    o = _get(c, obligation_id)
    if o["state"] not in ("received", "settled"):
        raise unprocessable("só obrigação recebida/liquidada é reembolsada", code="obligation_state")
    if int(refunded_cents) != int(o["received_cents"]):
        raise unprocessable("reembolso parcial é ajuste: registre a decisão e use o valor integral recebido aqui", code="partial_refund")
    _four_eyes(c, obligation_id, actor, ("received",))
    _set(c, obligation_id, "reversed", actor=actor)
    c.run("INSERT INTO remuneration_obligation_events(obligation_id, from_state, to_state, actor_id, note) VALUES ($1,$2,'reversed',$3,$4)",
          obligation_id, o["state"], actor, (f"reembolso de {refunded_cents} centavos (ref. {reference[:80]}): " + note)[:2000])
    return {"state": "reversed", "refunded_cents": int(refunded_cents)}


def reverse_for_source(c: Connection, *, source_kind: str, source_id: str, note: str) -> list[str]:
    """Base estornada (doação estornada/chargeback): obrigações não recebidas viram `reversed`; recebidas viram `disputed`."""
    rows = c.query("SELECT id::text AS id, state FROM remuneration_obligations WHERE source_kind = $1 AND source_id = $2", source_kind, source_id)
    out = []
    for r in rows:
        if r["state"] in ("calculated", "exempt", "due", "invoiced", "charged", "overdue"):
            _set(c, r["id"], "reversed")
            out.append(r["id"])
        elif r["state"] in ("received", "settled"):
            _set(c, r["id"], "disputed", dispute_reason="base estornada depois do recebimento: " + note[:1900])
            out.append(r["id"])
    return out


# ============================================================================ consultas
def org_view(c: Connection, org_id: str) -> dict:
    pol = policy(c)
    settled = settled_volume_12m(c, org_id)
    rows = c.query("SELECT id::text AS id, source_kind, source_id, campaign_id::text AS campaign_id, rule_key, basis_cents, amount_cents, funding_source,"
                   " public_fee_authorized, state, trigger_code, due_on, received_cents, platform_charge_id::text AS platform_charge_id, created_at"
                   " FROM remuneration_obligations WHERE org_id = $1 ORDER BY created_at DESC LIMIT 500", org_id)
    totals: dict[str, int] = {}
    for r in rows:
        totals[r["state"]] = totals.get(r["state"], 0) + int(r["amount_cents"])
    notices = c.query("SELECT id::text AS id, kind, body, sent_at, acknowledged_at FROM remuneration_notices WHERE org_id = $1 ORDER BY sent_at DESC LIMIT 50", org_id)
    return {
        "policy": {k: v for k, v in pol.items() if k != "id"},
        "settled_12m_cents": settled, "allowance_cents": int(pol.get("allowance_settled_cents_12m", 0)),
        "allowance_remaining_cents": max(0, int(pol.get("allowance_settled_cents_12m", 0)) - settled),
        "obligations": rows, "totals_by_state": totals, "notices": notices,
        "definitions": {
            "calculated": "calculada pela versão congelada; NÃO é devida nem receita",
            "exempt": "isenta (recurso público sem autorização, franquia, dispensa)",
            "due": "devida: regra ativa + franquia ultrapassada + aviso prévio dentro do prazo",
            "invoiced": "faturada à parte (nunca descontada de doação)", "charged": "cobrada", "received": "recebida com referência",
            "settled": "liquidada e conciliada", "reversed": "estornada", "overdue": "vencida — nenhum acesso é bloqueado",
            "disputed": "em disputa", "waived": "dispensada por decisão registrada"},
        "never_blocks": pol.get("never_blocks", []),
    }


def ack_notice(c: Connection, *, notice_id: str, org_id: str, user_id: str) -> None:
    if not c.run("UPDATE remuneration_notices SET acknowledged_at = now(), acknowledged_by = $3 WHERE id = $1 AND org_id = $2 AND acknowledged_at IS NULL",
                 notice_id, org_id, user_id):
        raise not_found("Aviso")


def platform_revenue_view(c: Connection) -> dict:
    """Receita PREVISTA (calculada) × DEVIDA × FATURADA × RECEBIDA × LIQUIDADA — nunca somadas num número só."""
    rows = c.query("SELECT state, count(*) AS n, coalesce(sum(amount_cents),0) AS cents, coalesce(sum(received_cents),0) AS received"
                   " FROM remuneration_obligations GROUP BY state")
    by = {r["state"]: {"count": int(r["n"]), "cents": int(r["cents"]), "received_cents": int(r["received"])} for r in rows}
    return {"by_state": by,
            "calculated_not_due_cents": by.get("calculated", {}).get("cents", 0),
            "due_cents": sum(by.get(s, {}).get("cents", 0) for s in ("due", "invoiced", "charged", "overdue")),
            "received_cents": sum(by.get(s, {}).get("received_cents", 0) for s in ("received", "settled")),
            "settled_cents": by.get("settled", {}).get("cents", 0),
            "note": "Nenhum destes números é receita reconhecida: só 'settled' é dinheiro conciliado na conta da plataforma."}

