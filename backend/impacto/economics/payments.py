"""Pagamento da plataforma: máquina de estados, trilha, parcelamento, PIX e boleto.

ESCOPO, E A DISTINÇÃO QUE NÃO PODE SE PERDER

Isto é a cobrança **da plataforma** contra a organização que a usa. Não confundir com
`payment_records`, que é o REGISTRO de aporte declarado ao projeto — ali o dinheiro nunca passa pela
plataforma (ADR-022/031), e é por isso que aquela tabela já aceitava 'pix' e 'boleto' sem existir
cobrança por PIX nenhuma. A auditoria econômica registrou essa confusão como o achado mais fácil de
cometer lendo o banco.

A REGRA QUE GOVERNA ESTE MÓDULO

Os documentos desta rodada: "Nunca apresentar pagamento fake como pagamento real" e
"PRODUCTION PAYMENT NOT CONFIGURED". A honestidade não é um aviso na tela: é `is_simulated`, coluna
**derivada** do provedor por gatilho, que ninguém escreve. Uma cobrança feita no provedor de teste fica
marcada como simulada para sempre, e `platform_revenue()` jamais a soma à receita real.

O ESTADO REAL, HOJE

**Nenhum provedor de pagamento está configurado.** Não há conta, chave nem identificador de preço.
Logo: nenhuma cobrança real foi processada por este código, e `is_simulated` é verdadeira em todas as
cobranças que existem. O que está pronto e testado é a camada da plataforma — máquina de estados,
trilha, idempotência de webhook, parcelamento, instrução de PIX e de boleto. Ligar o provedor é
configuração, não programação; e enquanto não houver, `status()` diz isso em letras.

PARCELAMENTO NÃO É ASSINATURA

Os documentos pedem a distinção explicitamente, e ela é concreta: parcelamento tem número fixo de
parcelas, vencimentos definidos, não renova, e a soma das parcelas tem de fechar com o total — há
gatilho de restrição postergada no banco conferindo isso. Assinatura renova, não tem fim previsto e
muda de preço com aviso de 30 dias.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection
from ..http import forbidden, not_found, unprocessable

#: Provedores que cobram de verdade. Lista EXPLÍCITA, espelhando o gatilho `charge_simulated_flag()`.
#: A versão permissiva ("todos menos sandbox") faria um dublê novo nascer marcado como real.
REAL_PROVIDERS = ("stripe",)
METHODS = ("card", "pix", "boleto", "manual")
KINDS = ("subscription", "one_off", "installment_plan", "operation")
STATES = ("created", "checkout_started", "pending", "authorized", "paid", "settled", "failed",
          "expired", "cancelled", "refunded", "partially_refunded", "disputed", "chargeback")
OPEN_STATES = ("created", "checkout_started", "pending", "authorized")
STATE_LABEL = {
    "created": "criada", "checkout_started": "checkout aberto", "pending": "aguardando pagamento",
    "authorized": "autorizada", "paid": "paga", "settled": "liquidada", "failed": "recusada",
    "expired": "vencida", "cancelled": "cancelada", "refunded": "devolvida",
    "partially_refunded": "devolvida em parte", "disputed": "contestada", "chargeback": "estornada",
}
METHOD_LABEL = {"card": "cartão", "pix": "PIX", "boleto": "boleto",
                "manual": "fora da plataforma (contrato)"}

NOT_CONFIGURED = "PRODUCTION PAYMENT NOT CONFIGURED"


def status(settings: Any) -> dict:
    """O que está e o que não está configurado. Chamado por toda resposta que fala de pagamento."""
    provider = getattr(settings, "billing_provider", None) or "none"
    real = provider in REAL_PROVIDERS
    has_key = bool(getattr(settings, "stripe_secret_key", None))
    return {
        "provider": provider,
        "is_real_provider": real,
        "configured": bool(real and has_key),
        "banner": None if (real and has_key) else NOT_CONFIGURED,
        "methods_implemented": list(METHODS),
        "methods_available_now": [] if not (real and has_key) else ["card"],
        "note": ("Nenhum provedor de pagamento está configurado nesta instalação: não há conta, chave "
                 "nem identificador de preço. A arquitetura de cartão, cartão parcelado, PIX e boleto "
                 "está implementada e testada do lado da plataforma, e toda cobrança criada aqui fica "
                 "marcada como SIMULADA — `platform_revenue()` nunca a soma à receita real."
                 if not (real and has_key) else
                 "Provedor configurado. Cobranças neste provedor contam como receita real."),
    }


def graph(conn: Connection) -> list[dict]:
    return conn.query("SELECT from_state, to_state, origin, note FROM charge_state_graph"
                      " ORDER BY from_state, to_state")


# ---------------------------------------------------------------------------- criar
def create(conn: Connection, *, org_id: str, actor: str | None, kind: str, method: str,
           amount_cents: int, currency: str, provider: str,
           subscription_id: str | None = None, invoice_id: str | None = None,
           billable_event_id: int | None = None, installments: int | None = None,
           instrument_id: str | None = None, due_on: Any = None,
           expires_at: Any = None) -> dict:
    """Abre uma cobrança em `created`. Nada é cobrado aqui: é o registro da intenção de cobrar."""
    if kind not in KINDS:
        raise unprocessable(f"Tipo de cobrança inválido: {kind}", {"possiveis": list(KINDS)})
    if method not in METHODS:
        raise unprocessable(f"Meio de pagamento inválido: {method}", {"possiveis": list(METHODS)})
    if kind == "installment_plan" and not installments:
        raise unprocessable("Parcelamento exige o número de parcelas", {"campo": "installments"})
    if installments and method != "card":
        raise unprocessable("Parcelamento só existe em cartão", {"campo": "method"})
    row = conn.one(
        "INSERT INTO platform_charges(org_id, subscription_id, invoice_id, billable_event_id, kind,"
        " method, amount_cents, currency, installments, instrument_id, provider, due_on, expires_at,"
        " created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)"
        " RETURNING id::text AS id, state, is_simulated, created_at",
        org_id, subscription_id, invoice_id, billable_event_id, kind, method, amount_cents,
        currency.upper(), installments, instrument_id, provider, due_on, expires_at, actor)
    return _decorate(row)


def set_installments(conn: Connection, *, charge_id: str, org_id: str,
                     schedule: list[dict]) -> dict:
    """Grava o cronograma. A soma tem de fechar com o total — o banco confere, não este código.

    A conferência é uma restrição POSTERGADA (`DEFERRABLE INITIALLY DEFERRED`): ela roda no fim da
    transação, não a cada parcela inserida. Sem isso, inserir a primeira de três parcelas já falharia,
    porque a soma parcial nunca fecha com o total.
    """
    c = conn.one("SELECT org_id::text AS org_id, installments, amount_cents FROM platform_charges"
                 " WHERE id = $1", charge_id)
    if not c:
        raise not_found("Cobrança")
    if c["org_id"] != org_id:
        raise forbidden("Esta cobrança é de outra organização")
    if not c["installments"]:
        raise unprocessable("Esta cobrança não é parcelada")
    if len(schedule) != c["installments"]:
        raise unprocessable(f"O cronograma precisa ter exatamente {c['installments']} parcelas",
                            {"enviadas": len(schedule), "esperadas": c["installments"]})
    for i, item in enumerate(schedule, start=1):
        conn.run("INSERT INTO charge_installments(charge_id, n, amount_cents, due_on)"
                 " VALUES ($1,$2,$3,$4) ON CONFLICT (charge_id, n) DO UPDATE"
                 " SET amount_cents = excluded.amount_cents, due_on = excluded.due_on",
                 charge_id, i, int(item["amount_cents"]), item["due_on"])
    return {"charge_id": charge_id, "installments": len(schedule)}


def attach_pix(conn: Connection, *, charge_id: str, payload: str, expires_at: Any,
               provider_txid: str | None = None) -> dict:
    """Guarda a instrução "copia e cola" do PIX gerada pelo provedor.

    A carga não é credencial: é instrução de pagamento com prazo, e não autoriza nada em nome de
    ninguém. Mas tem validade, e por isso `expires_at` é obrigatório na tabela.
    """
    conn.run("INSERT INTO charge_pix(charge_id, payload, expires_at, provider_txid)"
             " VALUES ($1,$2,$3,$4) ON CONFLICT (charge_id) DO UPDATE"
             " SET payload = excluded.payload, expires_at = excluded.expires_at,"
             " provider_txid = excluded.provider_txid", charge_id, payload, expires_at, provider_txid)
    return {"charge_id": charge_id, "expires_at": expires_at}


def attach_boleto(conn: Connection, *, charge_id: str, digitable_line: str, due_on: Any,
                  barcode: str | None = None, provider_boleto_id: str | None = None,
                  pdf_storage_key: str | None = None) -> dict:
    conn.run("INSERT INTO charge_boleto(charge_id, digitable_line, barcode, due_on,"
             " provider_boleto_id, pdf_storage_key) VALUES ($1,$2,$3,$4,$5,$6)"
             " ON CONFLICT (charge_id) DO UPDATE SET digitable_line = excluded.digitable_line,"
             " barcode = excluded.barcode, due_on = excluded.due_on", charge_id, digitable_line,
             barcode, due_on, provider_boleto_id, pdf_storage_key)
    return {"charge_id": charge_id, "due_on": due_on}


# ---------------------------------------------------------------------------- mover
def transition(conn: Connection, *, charge_id: str, to_state: str, org_id: str | None = None,
               provider_charge_id: str | None = None, refunded_cents: int | None = None,
               failure_code: str | None = None, failure_message: str | None = None,
               admin: bool = False) -> dict:
    """Move a cobrança. Quem recusa o que não está no grafo é o gatilho, não este código.

    `org_id` nulo significa origem de sistema (webhook): a RLS permite, e a trilha registra a origem
    como `webhook` porque `app_system()` é verdadeiro ali.
    """
    c = conn.one("SELECT org_id::text AS org_id, state, amount_cents FROM platform_charges"
                 " WHERE id = $1", charge_id)
    if not c:
        raise not_found("Cobrança")
    if org_id is not None and not admin and c["org_id"] != org_id:
        raise forbidden("Esta cobrança é de outra organização")
    if to_state not in STATES:
        raise unprocessable(f"Estado inválido: {to_state}", {"possiveis": list(STATES)})
    edge = conn.one("SELECT origin FROM charge_state_graph WHERE from_state = $1 AND to_state = $2",
                    c["state"], to_state)
    if not edge:
        options = [r["to_state"] for r in conn.query(
            "SELECT to_state FROM charge_state_graph WHERE from_state = $1 ORDER BY 1", c["state"])]
        raise unprocessable(
            f"De '{STATE_LABEL.get(c['state'], c['state'])}' não é possível ir para "
            f"'{STATE_LABEL.get(to_state, to_state)}'",
            {"de": c["state"], "possiveis": options}, code="invalid_transition")
    if to_state == "partially_refunded":
        if not refunded_cents or refunded_cents <= 0 or refunded_cents >= c["amount_cents"]:
            raise unprocessable("Devolução parcial exige valor entre zero e o total da cobrança",
                                {"total_cents": c["amount_cents"]}, code="bad_refund")
    row = conn.one(
        "UPDATE platform_charges SET state = $2,"
        " provider_charge_id = coalesce($3, provider_charge_id),"
        " refunded_cents = coalesce($4, refunded_cents),"
        " failure_code = coalesce($5, failure_code),"
        " failure_message = coalesce($6, failure_message)"
        " WHERE id = $1 RETURNING id::text AS id, state, is_simulated, paid_at, settled_at,"
        " refunded_cents", charge_id, to_state, provider_charge_id, refunded_cents, failure_code,
        failure_message)
    return _decorate(row)


def expire_due(conn: Connection) -> dict:
    """Vence PIX e boleto não pagos. Chamado por job; o estado `expired` está no grafo."""
    n = conn.run("UPDATE platform_charges SET state = 'expired'"
                 " WHERE state = 'pending'"
                 "   AND ((expires_at IS NOT NULL AND expires_at < now())"
                 "     OR (due_on IS NOT NULL AND due_on < current_date))")
    return {"expired": int(n or 0)}


# ---------------------------------------------------------------------------- leitura
def get(conn: Connection, *, charge_id: str, org_id: str | None) -> dict:
    c = conn.one(
        "SELECT id::text AS id, org_id::text AS org_id, kind, method, amount_cents, currency, state,"
        " installments, provider, provider_charge_id, is_simulated, due_on, expires_at, paid_at,"
        " settled_at, refunded_cents, failure_code, failure_message, created_at, updated_at,"
        " subscription_id::text AS subscription_id, invoice_id::text AS invoice_id,"
        " billable_event_id FROM platform_charges WHERE id = $1", charge_id)
    if not c:
        raise not_found("Cobrança")
    out = _decorate(c)
    out["events"] = conn.query(
        "SELECT from_state, to_state, origin, provider_event_id, amount_cents, note, at"
        " FROM charge_events WHERE charge_id = $1 ORDER BY id", charge_id)
    out["installments_schedule"] = conn.query(
        "SELECT n, amount_cents, due_on, state, paid_at FROM charge_installments"
        " WHERE charge_id = $1 ORDER BY n", charge_id)
    out["pix"] = conn.one("SELECT payload, expires_at, provider_txid FROM charge_pix"
                          " WHERE charge_id = $1", charge_id)
    out["boleto"] = conn.one("SELECT digitable_line, barcode, due_on, pdf_storage_key"
                             " FROM charge_boleto WHERE charge_id = $1", charge_id)
    return out


def mine(conn: Connection, *, org_id: str, state: str | None = None, limit: int = 25,
         offset: int = 0) -> dict:
    rows = conn.query(
        "SELECT id::text AS id, kind, method, amount_cents, currency, state, installments, provider,"
        " is_simulated, due_on, expires_at, paid_at, refunded_cents, created_at"
        " FROM platform_charges WHERE org_id = $1 AND ($2::text IS NULL OR state = $2)"
        " ORDER BY created_at DESC LIMIT $3 OFFSET $4", org_id, state, limit + 1, offset)
    more = len(rows) > limit
    return {"items": [_decorate(r) for r in rows[:limit]], "has_more": more,
            "limit": limit, "offset": offset}


def revenue(conn: Connection, *, since: Any = None, until: Any = None,
            provider_configured: bool = False) -> dict:
    """Receita apurada, com o simulado em colunas próprias.

    Somar simulado com real mostraria dinheiro que não entrou. A separação está na função SQL, não
    aqui, para que qualquer consulta que use a função herde a separação.
    """
    rows = conn.query("SELECT * FROM platform_revenue($1,$2)", since, until)
    # A assinatura corre por `invoices` desde a v0.11.0 e NÃO foi migrada para `platform_charges`:
    # duas tabelas escrevendo o mesmo dinheiro dariam dois números divergentes para a mesma pergunta.
    # Então ela aparece aqui em bloco PRÓPRIO, somada à parte, com a mesma regra de provedor real.
    subs = conn.query(
        "SELECT currency,"
        " coalesce(sum(amount_cents) FILTER (WHERE provider = ANY($3) AND status = 'paid'), 0)"
        "   AS real_paid_cents,"
        " count(*) FILTER (WHERE provider = ANY($3) AND status = 'paid') AS real_invoices,"
        " coalesce(sum(amount_cents) FILTER (WHERE NOT (provider = ANY($3)) AND status = 'paid'), 0)"
        "   AS simulated_cents,"
        " count(*) FILTER (WHERE NOT (provider = ANY($3)) AND status = 'paid') AS simulated_invoices,"
        " coalesce(sum(amount_cents) FILTER (WHERE status = 'open'), 0) AS open_cents"
        " FROM invoices"
        " WHERE ($1::timestamptz IS NULL OR created_at >= $1)"
        "   AND ($2::timestamptz IS NULL OR created_at < $2)"
        " GROUP BY currency ORDER BY currency",
        since, until, list(REAL_PROVIDERS) if provider_configured else [])
    return {
        "items": rows,
        "subscriptions": {
            "items": subs,
            "note": ("Assinatura é apurada em `invoices` e fica em bloco separado de propósito: "
                     "`platform_charges` cobre avulso, parcelado, PIX e boleto."
                     + (f" Provedor real: {', '.join(REAL_PROVIDERS)}; fatura em provedor de teste "
                        "conta como simulada." if provider_configured else
                        " SEM provedor configurado nesta instalação, NENHUMA fatura conta como "
                        "real — nem as que têm 'stripe' na coluna de provedor. Coluna dizendo "
                        "'stripe' não é prova de chave ao vivo, e é exatamente o que um cenário "
                        "de teste escreve. Classificar por nome de provedor foi o erro que o "
                        "teste `test_the_consolidated_total_contains_only_real_money` pegou.")),
        },
        "total_real_paid_cents_by_currency": _merge_real(rows, subs),
        "provider_configured": provider_configured,
        "note": ("`real_*` conta apenas cobranças em provedor real. `simulated_*` conta as de "
                 "provedor de teste e NUNCA entra no real. Nesta instalação não há provedor "
                 "configurado, então a receita real é zero por construção — e isso é o estado "
                 "verdadeiro, não um erro de apuração."),
    }


def _merge_real(charges: list[dict], invoices: list[dict]) -> dict:
    """Soma só o que é real, de cobrança e de fatura, por moeda. O simulado não entra em lugar nenhum."""
    out: dict[str, int] = {}
    for row in charges:
        out[row["currency"]] = out.get(row["currency"], 0) + int(row["real_paid_cents"] or 0)
    for row in invoices:
        out[row["currency"]] = out.get(row["currency"], 0) + int(row["real_paid_cents"] or 0)
    return out


def _decorate(row: dict) -> dict:
    out = dict(row)
    if "state" in out:
        out["state_label"] = STATE_LABEL.get(out["state"], out["state"])
    if "method" in out:
        out["method_label"] = METHOD_LABEL.get(out["method"], out["method"])
    if out.get("is_simulated"):
        # Em TODA cobrança simulada, e não só no resumo. Uma linha de extrato que não diz que é
        # simulada é uma linha que alguém vai somar.
        out["warning"] = (f"{NOT_CONFIGURED} — esta cobrança é simulada. Nenhum valor foi "
                          "movimentado e ela não entra na receita real.")
    return out


# ---------------------------------------------------------------------------- webhook
def record_webhook(conn: Connection, *, provider: str, event_id: str, event_type: str,
                   payload: dict, signature_verified: bool,
                   charge_id: str | None = None) -> dict:
    """Grava o evento do provedor, uma vez. Reentrega não produz efeito, e fica contada.

    O frontend NUNCA é fonte de verdade sobre pagamento: quem confirma é o webhook assinado. Evento sem
    assinatura válida é gravado para auditoria e marcado, mas não deve produzir efeito — a decisão de
    aplicar fica com quem chama, e `signature_verified` é a informação que ela precisa.
    """
    existing = conn.one("SELECT id::text AS id, status FROM billing_events"
                        " WHERE provider = $1 AND event_id = $2", provider, event_id)
    if existing:
        conn.run("UPDATE billing_events SET duplicate_count = duplicate_count + 1"
                 " WHERE id = $1", existing["id"])
        return {"id": existing["id"], "duplicate": True, "applied": False,
                "note": "Evento já recebido: reentrega contada e ignorada."}
    row = conn.one(
        "INSERT INTO billing_events(provider, event_id, type, payload, status, signature_verified,"
        " charge_id) VALUES ($1,$2,$3,$4::jsonb,$5,$6,$7)"
        " RETURNING id::text AS id, received_at",
        provider, event_id, event_type, payload,
        "received" if signature_verified else "rejected_signature", signature_verified, charge_id)
    return {**row, "duplicate": False, "applied": signature_verified,
            "note": None if signature_verified else
            "Assinatura não conferida: o evento foi gravado para auditoria e NÃO produziu efeito."}


def reconciliation(conn: Connection, *, days: int = 7) -> dict:
    """O que o provedor disse e o que a plataforma registrou — e onde os dois discordam.

    Reconciliação não é relatório bonito: é a pergunta "existe cobrança parada num estado que o
    provedor já resolveu?". Sem ela, uma reentrega perdida deixa dinheiro cobrado e acesso negado.
    """
    return {
        "events": conn.query(
            "SELECT provider, type, status, signature_verified, duplicate_count, count(*) AS n"
            " FROM billing_events WHERE received_at >= now() - make_interval(days => $1)"
            " GROUP BY 1,2,3,4,5 ORDER BY n DESC", days),
        "stuck_charges": conn.query(
            "SELECT id::text AS id, org_id::text AS org_id, state, method, provider, amount_cents,"
            " currency, is_simulated, created_at FROM platform_charges"
            " WHERE state IN ('checkout_started','pending','authorized')"
            "   AND created_at < now() - interval '2 days' ORDER BY created_at LIMIT 100"),
        "unverified_events": int(conn.scalar(
            "SELECT count(*) FROM billing_events WHERE NOT signature_verified"
            "   AND received_at >= now() - make_interval(days => $1)", days) or 0),
        "note": ("`stuck_charges` são cobranças abertas há mais de dois dias: webhook perdido, "
                 "checkout abandonado ou provedor fora do ar. `unverified_events` maior que zero "
                 "exige investigação — é tentativa de forjar confirmação de pagamento."),
    }
