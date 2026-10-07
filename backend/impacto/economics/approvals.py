"""Alçada de aprovação por valor.

O QUE NÃO EXISTIA

Nenhuma faixa de valor exigia aprovação em lugar nenhum da plataforma. Havia onze implementações
independentes de "quatro olhos" — montagem de documento, conteúdo editorial, regra fiscal, lote de
voucher, convênio, exceção de compra, responsabilidade — cada uma com o seu CHECK no banco e o seu
`raise` no handler. Nenhuma delas olhava para o VALOR: aprovar dez reais e aprovar cem mil passava
pelo mesmo caminho.

A ALÇADA É DADO

As faixas estão em `approval_policies` e `approval_rules`. Mudar a alçada é decisão de governança, e
exigir implantação para isso faz a decisão ser tomada por quem tem acesso ao servidor em vez de por
quem responde pelo dinheiro.

SEGREGAÇÃO DE FUNÇÃO, NÃO CONTAGEM DE CLIQUES

Quando uma faixa exige mais de uma permissão (`{finance.approve, accounting.close}`), as aprovações
têm de vir de permissões DIFERENTES. Duas aprovações do mesmo papel são duas pessoas com o mesmo
ponto cego. Imposto pelo gatilho `approval_no_self`, não por este módulo.
"""
from __future__ import annotations

from ..http import ApiError


def rule_for(c, operation: str, amount_cents: int) -> dict | None:
    """Qual faixa se aplica. None quando a operação não tem política ativa."""
    row = c.one("SELECT policy_id::text AS policy_id, approvals_needed, required_permissions"
                " FROM approval_rule_for($1, $2)", operation, amount_cents)
    return dict(row) if row else None


def request(c, *, operation: str, object_type: str, object_id: str, amount_cents: int,
            summary: str, requested_by: str, currency: str = "BRL") -> dict:
    """Abre o pedido de aprovação na faixa correta.

    Devolve `{"needed": 0}` quando a operação não tem política: ausência de política significa que
    ninguém definiu alçada para aquilo, e inventar uma aqui seria criar governança por acidente.
    """
    faixa = rule_for(c, operation, amount_cents)
    if not faixa:
        return {"needed": 0, "request_id": None,
                "note": f"Nenhuma política de aprovação ativa para '{operation}'."}
    row = c.one(
        "INSERT INTO approval_requests(policy_id, operation, object_type, object_id, amount_cents,"
        " currency, summary, approvals_needed, requested_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)"
        " RETURNING id::text, approvals_needed, state",
        faixa["policy_id"], operation, object_type, object_id, amount_cents, currency, summary,
        faixa["approvals_needed"], requested_by)
    return {"needed": int(row["approvals_needed"]), "request_id": row["id"],
            "state": row["state"], "required_permissions": faixa["required_permissions"]}


def decide(c, ac, *, request_id: str, approve: bool, permission_used: str,
           note: str | None = None) -> dict:
    """Registra uma decisão. O fechamento do pedido é do gatilho, não daqui.

    Contar "quantas faltam" na aplicação é a conta que diverge quando duas aprovações chegam no
    mesmo instante. O gatilho `approval_settle` conta dentro da transação.
    """
    pedido = c.one("SELECT operation, amount_cents, state, requested_by::text AS requested_by,"
                   " approvals_needed FROM approval_requests WHERE id = $1", request_id)
    if not pedido:
        raise ApiError(404, "approval_not_found", "Pedido de aprovação não encontrado.")
    if pedido["state"] != "pending":
        raise ApiError(409, "approval_not_pending", f"Este pedido está {pedido['state']}.")

    faixa = rule_for(c, pedido["operation"], pedido["amount_cents"])
    permitidas = set(faixa["required_permissions"]) if faixa else set()
    if permission_used not in permitidas:
        raise ApiError(403, "permission_not_in_band",
                       "Esta faixa de valor não é aprovada por esta permissão.",
                       {"required_permissions": sorted(permitidas)})
    if not ac.has_permission(permission_used):
        raise ApiError(403, "permission_denied", "Você não tem a permissão que informou.",
                       {"required_permission": permission_used})

    c.run("INSERT INTO approval_decisions(request_id, decided_by, decision, permission_used, note)"
          " VALUES ($1,$2,$3,$4,$5)",
          request_id, ac.user_id, "approve" if approve else "reject", permission_used, note)
    depois = c.one("SELECT state, (SELECT count(*) FROM approval_decisions d"
                   "  WHERE d.request_id = $1 AND d.decision = 'approve') AS aprovadas,"
                   " approvals_needed FROM approval_requests WHERE id = $1", request_id)
    return {"state": depois["state"], "approvals": int(depois["aprovadas"]),
            "needed": int(depois["approvals_needed"])}


def is_approved(c, *, object_type: str, object_id: str, operation: str) -> bool:
    return bool(c.one("SELECT 1 FROM approval_requests WHERE object_type = $1 AND object_id = $2"
                      " AND operation = $3 AND state = 'approved'",
                      object_type, object_id, operation))


def require_approved(c, *, object_type: str, object_id: str, operation: str,
                     amount_cents: int) -> None:
    """Exige aprovação concluída antes de a operação prosseguir.

    Quando a faixa não exige aprovação nenhuma (valor baixo, política de uma aprovação já
    satisfeita), passa. Quando exige e não há, recusa dizendo quantas faltam — a tela precisa poder
    mostrar "aguardando 2ª aprovação" em vez de um erro genérico.
    """
    if is_approved(c, object_type=object_type, object_id=object_id, operation=operation):
        return
    faixa = rule_for(c, operation, amount_cents)
    if not faixa:
        return
    pendente = c.one("SELECT id::text AS id, approvals_needed,"
                     " (SELECT count(*) FROM approval_decisions d WHERE d.request_id = q.id"
                     "  AND d.decision = 'approve') AS aprovadas"
                     " FROM approval_requests q WHERE object_type = $1 AND object_id = $2"
                     "   AND operation = $3 AND state = 'pending'",
                     object_type, object_id, operation)
    raise ApiError(409, "approval_required",
                   "Esta operação está na faixa que exige aprovação.",
                   {"operation": operation, "amount_cents": amount_cents,
                    "approvals_needed": int(faixa["approvals_needed"]),
                    "approvals_given": int(pendente["aprovadas"]) if pendente else 0,
                    "required_permissions": faixa["required_permissions"],
                    "request_id": pendente["id"] if pendente else None})


def pending(c, limit: int = 100) -> list[dict]:
    return [dict(r) for r in c.query(
        "SELECT q.id::text AS id, q.operation, q.object_type, q.object_id, q.amount_cents,"
        " q.currency, q.summary, q.approvals_needed, q.created_at, u.email AS requested_by,"
        " (SELECT count(*) FROM approval_decisions d WHERE d.request_id = q.id"
        "  AND d.decision = 'approve') AS approvals_given,"
        " (SELECT array_agg(dd.permission_used) FROM approval_decisions dd"
        "  WHERE dd.request_id = q.id) AS permissions_used"
        " FROM approval_requests q JOIN users u ON u.id = q.requested_by"
        " WHERE q.state = 'pending' ORDER BY q.created_at LIMIT $1", limit)]
