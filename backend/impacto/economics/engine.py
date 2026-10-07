"""Motor financeiro: CALCULA · INSTRUI · CONCILIA.

A REGRA QUE GOVERNA ESTE MÓDULO

`NON_CUSTODIAL_ARCHITECTURE.md` (ADR-284). A plataforma não guarda dinheiro de outra pessoa. Ela faz
três coisas, e nenhuma delas é mover valor:

    CALCULA   quanto é devido, a quem, por qual regra, com qual base
    INSTRUI   emite a INSTRUÇÃO de pagamento para quem paga executar
    CONCILIA  confronta o esperado com o que de fato aconteceu

Por isso não há aqui `payout`, `split`, `recipient` nem carteira. Há `payment_instructions`, que é
documento. A diferença prática é a autorização do Banco Central que não precisamos ter.

CAIXA ≠ COMPETÊNCIA

Uma assinatura anual recebida em janeiro é caixa de janeiro e competência de doze meses. Tratar as
duas como a mesma coisa faz janeiro parecer extraordinário e dezembro parecer um desastre, e
nenhuma das duas leituras é verdade. Os lançamentos carregam `period` (competência) e `cash_date`
(caixa) separados, e os relatórios escolhem qual deles usar — explicitamente.
"""
from __future__ import annotations

import uuid

from ..http import ApiError

# Contas usadas pelo reconhecimento automático. Nomeadas aqui para que mudar o plano de contas
# quebre o teste em vez de produzir lançamento numa conta que deixou de existir.
ACC_CLIENTS_RECEIVABLE = "1.2.1"
ACC_DEFERRED_REVENUE = "2.2.1"
ACC_SUBSCRIPTION_REVENUE = "4.1.1"
ACC_USAGE_REVENUE = "4.2.1"
ACC_MARKETPLACE_FEE = "4.4.1"
ACC_AI_COST = "5.1.2"
ACC_CASH = "1.1.1"


# ------------------------------------------------------------------------------------------------
# CALCULA
# ------------------------------------------------------------------------------------------------

def compute_marketplace_fee(c, *, contract_amount_cents: int) -> dict:
    """Quanto a plataforma cobraria de taxa sobre um serviço contratado.

    CALCULA, e não cobra. A regra `marketplace.take_rate` está `active = false` e é recusada pelo
    banco enquanto valer a ADR-022: sem custódia, a plataforma não vê o valor passar, então a base
    de cálculo seria a declaração de uma das partes.

    O que esta função devolve é o que SERIA devido se a regra fosse ligada — útil para a proposta
    comercial e para o modelo financeiro, inútil como cobrança. O campo `billable` diz isso.
    """
    regra = c.one("SELECT key, percentage, active, legal_status FROM monetization_rules"
                  " WHERE key = 'marketplace.take_rate'")
    if not regra:
        return {"billable": False, "reason": "rule_missing"}
    pct = regra["percentage"]
    # DOIS motivos diferentes, e confundi-los foi o que fez a documentação afirmar que havia "a
    # regra de 10%": não há percentual nenhum declarado. Enquanto `percentage` é nulo, esta função
    # não calcula — ela não tem o que calcular, e dizer "calculado" seria inventar a alíquota.
    if pct is None:
        return {
            "billable": False,
            "reason": "percentage_not_declared",
            "legal_status": regra["legal_status"],
            "percentage": None,
            "base_cents": contract_amount_cents,
            "fee_cents": None,
            "note": ("Não há alíquota declarada para `marketplace.take_rate`: a regra existe com "
                     "`percentage = NULL` e `active = false`. Não há cálculo a devolver — e "
                     "devolver um número aqui seria inventar a alíquota. Quando houver decisão "
                     "comercial, o percentual entra no DADO e esta função passa a calcular, sem "
                     "mudar de código. Ver NON_CUSTODIAL_ARCHITECTURE.md §4."),
        }
    fee = int(contract_amount_cents * float(pct) / 100)
    return {
        "billable": bool(regra["active"]),
        "reason": "ok" if regra["active"] else "rule_inactive",
        "legal_status": regra["legal_status"],
        "percentage": float(pct),
        "base_cents": contract_amount_cents,
        "fee_cents": fee,
        "note": ("Valor CALCULADO, não cobrável: a regra está inativa e o banco recusa ativá-la "
                 "enquanto a plataforma não custodiar o valor (ADR-022). Ver "
                 "NON_CUSTODIAL_ARCHITECTURE.md §4 para o caminho sem custódia.")
        if not regra["active"] else "Regra ativa.",
    }


def recognition_schedule(*, amount_cents: int, months: int, first_period) -> list[dict]:
    """Divide um valor faturado nas competências em que ele é incorrido.

    A sobra da divisão vai na PRIMEIRA competência, não na última. Duas razões: o total fecha
    exatamente, e o mês que já passou não muda depois — se a sobra fosse na última, uma mudança de
    prazo reabriria a conta de um mês fechado.
    """
    if months < 1:
        raise ValueError("competências devem ser pelo menos uma")
    base, resto = divmod(amount_cents, months)
    return [{"month_index": i, "amount_cents": base + (resto if i == 0 else 0)}
            for i in range(months)]


def post_batch(c, *, entries: list[dict], created_by: str | None = None) -> str:
    """Grava um lote de lançamentos e exige que ele feche.

    Lote desbalanceado é erro de lançamento, e um balancete que não fecha não é informação. A
    conferência acontece DENTRO da transação: aceitar o lote e conferir depois deixaria o banco com
    o erro gravado.
    """
    if not entries:
        raise ValueError("lote vazio")
    lote = str(uuid.uuid4())
    for e in entries:
        c.run("INSERT INTO accounting_entries(period, account_code, cost_center, batch_id, side,"
              " amount_cents, currency, description, source_kind, source_id, cash_date, created_by)"
              " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
              e["period"], e["account_code"], e.get("cost_center"), lote, e["side"],
              e["amount_cents"], e.get("currency", "BRL"), e["description"],
              e["source_kind"], e.get("source_id"), e.get("cash_date"), created_by)
    if not c.scalar("SELECT batch_is_balanced($1)", lote):
        raise ApiError(422, "batch_not_balanced",
                       "O lote não fecha: a soma dos débitos tem de igualar a dos créditos.")
    return lote


def ensure_period(c, period) -> None:
    """Abre a competência se ela ainda não existe. Não reabre competência fechada."""
    c.run("INSERT INTO accounting_periods(period) VALUES (date_trunc('month', $1::date)::date)"
          " ON CONFLICT DO NOTHING", period)


def close_period(c, *, period, closed_by: str, note: str | None = None) -> dict:
    """Fecha a competência. É o que torna o número de um mês citável depois.

    Recusa fechar com lote desbalanceado: fechar um mês que não fecha é publicar um número errado
    com carimbo de definitivo.
    """
    abertos = [r["batch_id"] for r in c.query(
        "SELECT DISTINCT batch_id FROM accounting_entries WHERE period = $1", period)]
    quebrados = [b for b in abertos if not c.scalar("SELECT batch_is_balanced($1)", b)]
    if quebrados:
        raise ApiError(409, "unbalanced_batches",
                       "Há lotes que não fecham nesta competência.",
                       {"batches": [str(b) for b in quebrados[:20]]})
    row = c.one("UPDATE accounting_periods SET status = 'closed', closed_at = now(), closed_by = $2,"
                " note = coalesce($3, note)"
                " WHERE period = $1 AND status <> 'closed' RETURNING period, closed_at, note",
                period, closed_by, note)
    if not row:
        raise ApiError(409, "period_not_open",
                       "Esta competência não está aberta: ou já foi fechada, ou nunca existiu.")
    return {"period": row["period"], "closed_at": row["closed_at"], "note": row["note"]}


# ------------------------------------------------------------------------------------------------
# INSTRUI
# ------------------------------------------------------------------------------------------------

def create_instruction(c, *, kind: str, payee_name: str, amount_cents: int, due_on,
                       reference: str, created_by: str, payee_doc: str | None = None,
                       payer_org_id: str | None = None, account_code: str | None = None,
                       cost_center: str | None = None, expense_id: str | None = None,
                       idempotency_key: str | None = None) -> dict:
    """Cria a instrução em rascunho e abre o pedido de aprovação na faixa do valor."""
    row = c.one(
        "INSERT INTO payment_instructions(kind, payer_org_id, payee_name, payee_doc, amount_cents,"
        " due_on, reference, account_code, cost_center, expense_id, created_by, idempotency_key)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)"
        " RETURNING id::text, state, amount_cents",
        kind, payer_org_id, payee_name, payee_doc, amount_cents, due_on, reference,
        account_code, cost_center, expense_id, created_by, idempotency_key)
    from . import approvals
    ap = approvals.request(c, operation="payment_instruction", object_type="payment_instruction",
                           object_id=row["id"], amount_cents=amount_cents,
                           summary=f"{kind}: {payee_name} — {reference}", requested_by=created_by)
    if ap["needed"]:
        c.run("UPDATE payment_instructions SET state = 'pending_approval' WHERE id = $1", row["id"])
    return {"id": row["id"], "amount_cents": int(row["amount_cents"]), "approval": ap}


def issue_instruction(c, *, instruction_id: str) -> dict:
    """Emite a instrução — só depois de aprovada na faixa dela.

    A partir daqui, valor e destinatário congelam (gatilho `instruction_frozen_after_issue`). Para
    corrigir, cancela-se com motivo e emite-se outra, como se faz com documento que já saiu.
    """
    i = c.one("SELECT amount_cents, state FROM payment_instructions WHERE id = $1", instruction_id)
    if not i:
        raise ApiError(404, "instruction_not_found", "Instrução não encontrada.")
    if i["state"] not in ("draft", "pending_approval", "approved"):
        raise ApiError(409, "instruction_not_issuable", f"Instrução está {i['state']}.")
    from . import approvals
    approvals.require_approved(c, object_type="payment_instruction", object_id=instruction_id,
                               operation="payment_instruction", amount_cents=i["amount_cents"])
    row = c.one("UPDATE payment_instructions SET state = 'issued', issued_at = now()"
                " WHERE id = $1 RETURNING id::text, issued_at, amount_cents, payee_name, due_on,"
                " reference", instruction_id)
    return dict(row)


def record_execution(c, *, instruction_id: str, evidence_doc: str) -> dict:
    """Registra que QUEM PAGA executou, com a evidência.

    `evidence_doc` é obrigatório por restrição de tabela. Marcar como executada sem evidência seria
    a plataforma afirmando um pagamento que ela não viu — e ela nunca vê, por desenho.
    """
    row = c.one("UPDATE payment_instructions SET state = 'executed', executed_at = now(),"
                " evidence_doc = $2 WHERE id = $1 AND state = 'issued'"
                " RETURNING id::text, state, executed_at, amount_cents, evidence_doc",
                instruction_id, evidence_doc)
    if not row:
        raise ApiError(409, "instruction_not_issued",
                       "Só uma instrução emitida pode ser registrada como executada.")
    return dict(row)


# ------------------------------------------------------------------------------------------------
# CONCILIA
# ------------------------------------------------------------------------------------------------

def reconcile(c, *, days: int = 30) -> dict:
    """Confronta o esperado com o que aconteceu, e APONTA a diferença.

    Não corrige nada. Conciliação que corrige sozinha é conciliação que esconde o problema que ela
    existia para mostrar.
    """
    instrucoes_vencidas = [dict(r) for r in c.query(
        "SELECT id::text AS id, payee_name, amount_cents, due_on, state"
        " FROM payment_instructions"
        " WHERE state IN ('issued','approved') AND due_on < current_date"
        " ORDER BY due_on LIMIT 200")]
    sem_evidencia = [dict(r) for r in c.query(
        "SELECT id::text AS id, payee_name, amount_cents, executed_at FROM payment_instructions"
        " WHERE state = 'executed' AND evidence_doc IS NULL LIMIT 200")]
    despesas_sem_lancamento = [dict(r) for r in c.query(
        "SELECT e.id::text AS id, e.description, e.amount_cents, e.period"
        " FROM platform_expenses e"
        " WHERE e.status = 'paid' AND NOT EXISTS ("
        "   SELECT 1 FROM accounting_entries a WHERE a.source_kind = 'manual'"
        "     AND a.source_id = e.id::text)"
        " AND e.period >= date_trunc('month', current_date - make_interval(days => $1))::date LIMIT 200", days)]
    lotes_quebrados = [str(r["batch_id"]) for r in c.query(
        "SELECT DISTINCT batch_id FROM accounting_entries"
        " WHERE created_at > now() - make_interval(days => $1)", days)
        if not c.scalar("SELECT batch_is_balanced($1)", r["batch_id"])]
    # A conciliação de cobrança do provedor já existia e continua valendo; aqui ela é reaproveitada
    # em vez de reescrita.
    from . import payments as PAY
    cobranca = PAY.reconciliation(c, days=min(days, 30))
    return {
        "window_days": days,
        "overdue_instructions": instrucoes_vencidas,
        "executed_without_evidence": sem_evidencia,
        "paid_expenses_without_entry": despesas_sem_lancamento,
        "unbalanced_batches": lotes_quebrados,
        "charges": cobranca,
        "divergences": (len(instrucoes_vencidas) + len(sem_evidencia)
                        + len(despesas_sem_lancamento) + len(lotes_quebrados)),
        "note": "A conciliação APONTA; não corrige. Correção é lançamento com autor e motivo.",
    }
