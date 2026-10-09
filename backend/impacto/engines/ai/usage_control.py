"""AI Usage & Cost Control (v0.28.0, ADR-347): a camada por onde TODA operação de IA passa.

Responde, para cada pedido: quem é (usuário, organização, tipo, papel), o que pede (operação do
catálogo versionado), quanto custa (créditos pela regra da operação; centavos pela tabela de preço do
provedor, quando existe), DE ONDE SAI o dinheiro (gratuito → patrocínio → cota promocional → crédito
comprado → recusa com opções) e em que estado a execução está:

    created → authorized → reserved → running → succeeded | failed | partial | cancelled → reconciled

Garantias (provadas em tests/test_v0280_ai_usage_control.py):
  * nenhum débito sem execução SUCCEEDED; falha, parcial e cancelamento não cobram;
  * reserva é descontada do disponível; duas execuções simultâneas não gastam o mesmo crédito;
  * idempotência por (organização, chave): repetir o mesmo pedido devolve a mesma execução;
  * patrocínio esgotado ou encerrado NUNCA migra para cobrança do beneficiário em silêncio;
  * o frontend não escolhe preço, saldo nem fonte: tudo nasce aqui e é gravado na execução.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import time
from typing import Any

from ...http import ApiError, forbidden, not_found, unprocessable

ENGINE_VERSION = "usage-control@1.0"

FUNDING_LABEL = {
    "free": "gratuita (sem custo externo)",
    "promotional": "cota gratuita da organização",
    "purchased": "créditos comprados",
    "sponsorship": "patrocínio",
    "cached": "resultado já calculado (sem nova cobrança)",
}


def params_hash(params: dict) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def current_operation(conn, code: str) -> dict:
    op = conn.one("SELECT (ai_operation_current($1)).*", code)
    if not op or op.get("code") is None:
        raise not_found("Operação de IA")
    return op


def credits_for(op: dict, units: int) -> int:
    """base + por unidade × unidades (ex.: conjunto = 99 + 10 por projeto comparado)."""
    return int(op["credits_base"]) + int(op["credits_per_unit"]) * int(units)


# ------------------------------------------------------------------------------------------------ cotas (concessão preguiçosa)
def grant_due_quotas(conn, ctx) -> list[dict]:
    """Concede, uma vez, as cotas configuradas que a organização ainda não recebeu.

    A concessão é preguiçosa (no primeiro uso), auditada (ai_quota_grants) e anti-abuso: a cota de
    boas-vindas é uma por organização E uma por pessoa — criar outra organização não a renova.
    """
    out = []
    kind = ctx.principal.org_kind
    pols = conn.query("SELECT * FROM ai_quota_policies WHERE active AND $1 = ANY(applies_to_kinds)"
                      "   AND valid_from <= current_date AND (valid_until IS NULL OR valid_until >= current_date)"
                      " ORDER BY id", kind)
    for pol in pols:
        period_key = "once" if pol["period"] == "once" else time.strftime("%Y-%m")
        ja = conn.one("SELECT 1 FROM ai_quota_grants WHERE policy_id = $1 AND org_id = $2 AND period_key = $3",
                      pol["id"], ctx.org_id, period_key)
        if ja:
            continue
        if pol["one_per_user"] and conn.scalar("SELECT ai_quota_user_has($1, $2, $3)", pol["id"], ctx.user_id, period_key):
            continue
        n = conn.scalar("SELECT count(*) FROM ai_quota_grants WHERE policy_id = $1 AND org_id = $2", pol["id"], ctx.org_id)
        if n >= pol["max_grants_per_org"] and pol["period"] == "once":
            continue
        ledger_id = conn.scalar(
            "SELECT ai_credit_post($1, $2, 'grant', 'promotional', 'ai_quota_policy', $3, $4, $5, NULL,"
            "        CASE WHEN $6::int IS NULL THEN NULL ELSE now() + make_interval(days => $6::int) END)",
            ctx.org_id, pol["credits"], str(pol["id"]), f"quota:{pol['key']}:{ctx.org_id}:{period_key}",
            f"Cota: {pol['label_pt']}", pol["validity_days"])
        if not ledger_id:
            continue
        conn.run("INSERT INTO ai_quota_grants(policy_id, org_id, user_id, period_key, ledger_id) VALUES ($1,$2,$3,$4,$5)",
                 pol["id"], ctx.org_id, ctx.user_id if pol["one_per_user"] else None, period_key, ledger_id)
        out.append({"policy": pol["key"], "credits": pol["credits"], "period_key": period_key})
    return out


# ------------------------------------------------------------------------------------------------ saldos
def balances(conn, org_id: str) -> dict:
    prom = conn.scalar("SELECT ai_credit_balance_bucket($1, 'promotional')", org_id)
    comp = conn.scalar("SELECT ai_credit_balance_bucket($1, 'purchased')", org_id)
    return {
        "promotional": {"balance": prom, "reserved": conn.scalar("SELECT ai_credit_reserved($1,'promotional')", org_id),
                        "available": conn.scalar("SELECT ai_credit_available($1,'promotional')", org_id)},
        "purchased": {"balance": comp, "reserved": conn.scalar("SELECT ai_credit_reserved($1,'purchased')", org_id),
                      "available": conn.scalar("SELECT ai_credit_available($1,'purchased')", org_id)},
    }


def eligible_sponsorships(conn, ctx, op: dict, project_id: str | None, credits: int) -> list[dict]:
    """Patrocínios ativos que cobrem esta organização, esta operação e este valor — com limites por
    organização e por projeto conferidos contra o consumo já registrado."""
    rows = conn.query(
        "SELECT s.*, s.id::text AS id, s.sponsor_org_id::text AS sponsor_org_id, ai_sponsorship_used(s.id) AS used,"
        "       o.legal_name AS sponsor_name"
        "  FROM ai_sponsorships s JOIN organizations o ON o.id = s.sponsor_org_id"
        " WHERE s.status = 'active' AND s.starts_on <= current_date AND s.ends_on >= current_date"
        "   AND $1 = ANY(s.eligible_kinds)"
        "   AND (cardinality(s.eligible_org_ids) = 0 OR $2::uuid = ANY(s.eligible_org_ids))"
        "   AND (s.operations = '{*}' OR $3 = ANY(s.operations))"
        "   AND s.sponsor_org_id <> $2::uuid"
        " ORDER BY s.ends_on, s.created_at", ctx.principal.org_kind, ctx.org_id, op["code"])
    ok = []
    for s in rows:
        if s["eligible_uf"]:
            uf = conn.scalar("SELECT uf FROM organizations WHERE id = $1", ctx.org_id)
            if (uf or "").upper() != s["eligible_uf"].upper():
                continue
        remaining = int(s["budget_credits"]) - int(s["used"])
        if remaining < credits:
            continue
        if s["per_org_limit"] is not None:
            used_org = conn.scalar("SELECT ai_sponsorship_used($1, $2, NULL)", s["id"], ctx.org_id)
            if int(used_org) + credits > s["per_org_limit"]:
                continue
        if s["per_project_limit"] is not None and project_id:
            used_p = conn.scalar("SELECT ai_sponsorship_used($1, NULL, $2)", s["id"], project_id)
            if int(used_p) + credits > s["per_project_limit"]:
                continue
        ok.append({"id": s["id"], "name": s["name_pt"], "sponsor_name": s["sponsor_name"], "remaining": remaining,
                   "ends_on": s["ends_on"], "accountability": s["accountability_pt"]})
    return ok


# ------------------------------------------------------------------------------------------------ custo em centavos (estimativa)
def estimate_cost_cents(conn, ctx, op: dict, input_chars: int) -> tuple[Any, str]:
    """Centavos estimados pela tabela de preço do provedor; 'local_no_cost' para motor local;
    'no_price_table' quando o provedor externo não tem preço vigente (nunca zero)."""
    if op["provider_mode"] == "local" or ctx.app.ai.external is None:
        return 0, "local_no_cost"
    preco = conn.one("SELECT input_per_mtok_cents, output_per_mtok_cents FROM ai_price_table"
                     " WHERE provider = $1 AND (model = $2 OR $2 IS NULL) AND effective_from <= current_date"
                     "   AND (effective_until IS NULL OR effective_until >= current_date)"
                     " ORDER BY effective_from DESC LIMIT 1", ctx.app.ai.provider_name, ctx.app.settings.ai_model or None)
    if not preco:
        return None, "no_price_table"
    pol = conn.one("SELECT max_output_tokens FROM ai_model_policies WHERE tier = $1", op["tier"])
    tokens_in = max(1, input_chars // 4)
    cents = round(tokens_in * preco["input_per_mtok_cents"] / 1_000_000 + pol["max_output_tokens"] * preco["output_per_mtok_cents"] / 1_000_000, 4)
    return cents, "estimated"


# ------------------------------------------------------------------------------------------------ prévia e autorização
def _check_access(ctx, op: dict) -> None:
    if ctx.principal.org_kind not in op["allowed_kinds"] and not ctx.admin_mode:
        raise forbidden(f"A operação '{op['name_pt']}' não está disponível para organizações do tipo "
                        f"'{ctx.principal.org_kind}'", code="ai_operation_not_for_kind")
    ctx.require_role(op["min_role"])
    if op["status"] == "retired":
        raise ApiError(410, "ai_operation_retired", "Esta operação foi aposentada")
    if op["status"] == "planned":
        raise ApiError(501, "ai_operation_not_implemented",
                       f"'{op['name_pt']}' está no catálogo e NÃO está implementada: {op['completion_rule_pt']}")


def preview(conn, ctx, code: str, *, units: int = 1, input_chars: int = 0, project_id: str | None = None,
            cached: bool = False) -> dict:
    """Tudo o que a pessoa precisa saber ANTES de confirmar: o que será feito, quanto custa, quem paga,
    saldo, limites, o que recebe — e, quando não dá, por quê e o que pode fazer."""
    op = current_operation(conn, code)
    _check_access(ctx, op)
    if units < 1 or units > op["max_units"]:
        raise unprocessable(f"Esta operação aceita de 1 a {op['max_units']} {op['unit_label_pt']}(s)",
                            {"max_units": op["max_units"]}, code="ai_units_out_of_range")
    if input_chars > op["max_input_chars"]:
        raise unprocessable(f"Entrada acima do limite da operação ({op['max_input_chars']} caracteres)",
                            {"max_input_chars": op["max_input_chars"], "input_chars": input_chars}, code="ai_input_too_large")
    granted = grant_due_quotas(conn, ctx)
    credits = credits_for(op, units)
    bal = balances(conn, ctx.org_id)
    cents, cost_status = estimate_cost_cents(conn, ctx, op, input_chars)
    base = {"operation": {"code": op["code"], "version": op["version"], "name": op["name_pt"], "category": op["category"],
                          "tier": op["tier"], "status": op["status"], "delivers": op["delivers_pt"],
                          "completion_rule": op["completion_rule_pt"], "failure_policy": op["failure_policy"],
                          "price_is_hypothesis": op["status"] == "hypothesis", "provider_mode": op["provider_mode"]},
            "units": units, "unit_label": op["unit_label_pt"], "credits_required": credits,
            "estimated_cost_cents": cents, "cost_status": cost_status,
            "balances": bal, "quotas_granted_now": granted, "engine_version": ENGINE_VERSION}
    if cached:
        return base | {"allowed": True, "funding_source": "cached", "funding_label": FUNDING_LABEL["cached"], "credits_required": 0}
    if credits == 0 and "free" in op["funding_modes"]:
        return base | {"allowed": True, "funding_source": "free", "funding_label": FUNDING_LABEL["free"]}
    if "sponsorship" in op["funding_modes"] and op["sponsor_eligible"]:
        pats = eligible_sponsorships(conn, ctx, op, project_id, credits)
        if pats:
            return base | {"allowed": True, "funding_source": "sponsorship", "sponsorship": pats[0],
                           "funding_label": f"{FUNDING_LABEL['sponsorship']}: {pats[0]['name']} ({pats[0]['sponsor_name']})",
                           "message": "Esta operação será custeada pela iniciativa patrocinadora indicada. Você não será cobrado por ela."}
    if "free_quota" in op["funding_modes"] and op["free_quota_eligible"] and bal["promotional"]["available"] >= credits:
        return base | {"allowed": True, "funding_source": "promotional", "funding_label": FUNDING_LABEL["promotional"],
                       "message": "Você ainda pode realizar esta operação com a sua cota disponível."}
    if "credits" in op["funding_modes"] and bal["purchased"]["available"] >= credits:
        return base | {"allowed": True, "funding_source": "purchased", "funding_label": FUNDING_LABEL["purchased"],
                       "message": f"Serão usados {credits} créditos comprados. Saldo disponível: {bal['purchased']['available']}."}
    return base | {"allowed": False, "funding_source": None,
                   "message": ("Esta operação exige mais do que a sua cota e os seus créditos cobrem. "
                               "O custo está acima; nada será executado sem a sua decisão."),
                   "options": [{"kind": "buy_credits", "label": "Comprar créditos (PIX)", "link": "/ia"},
                               {"kind": "request_sponsorship", "label": "Verificar patrocínio disponível", "link": "/ia"},
                               {"kind": "save_draft", "label": "Continuar sem IA (seu trabalho fica salvo)"}]}


def authorize(conn, ctx, code: str, *, params: dict, units: int = 1, input_chars: int = 0,
              project_id: str | None = None, subject_ref: str | None = None,
              idempotency_key: str | None = None, cached: bool = False) -> dict:
    """Cria a execução em `reserved` (ou devolve a existente pela chave de idempotência).

    Reserva = estado da execução, não lançamento: o disponível já a desconta, e nada vai ao razão
    até SUCCEEDED. Lança 402 com a prévia inteira quando não há fonte de custeio.
    """
    if idempotency_key:
        ja = conn.one("SELECT * FROM ai_executions WHERE org_id = $1 AND idempotency_key = $2", ctx.org_id, idempotency_key)
        if ja:
            return _row(ja) | {"idempotent_replay": True}
    pv = preview(conn, ctx, code, units=units, input_chars=input_chars, project_id=project_id, cached=cached)
    if not pv["allowed"]:
        raise ApiError(402, "ai_funding_required", pv["message"], {k: pv[k] for k in ("credits_required", "balances", "options", "operation")})
    op = pv["operation"]
    credits = pv["credits_required"]
    fs = pv["funding_source"]
    # bloqueio consultivo por organização: duas autorizações simultâneas não reservam o mesmo crédito
    conn.run("SELECT pg_advisory_xact_lock(hashtext('ai_credit:' || $1))", ctx.org_id)
    if fs in ("promotional", "purchased"):
        disponivel = conn.scalar("SELECT ai_credit_available($1, $2)", ctx.org_id, fs)
        if disponivel < credits:
            raise ApiError(402, "ai_funding_required", "O saldo disponível mudou enquanto a operação era autorizada; confira e tente de novo.",
                           {"credits_required": credits, "available": disponivel, "funding_source": fs})
    row = conn.one(
        "INSERT INTO ai_executions(org_id, user_id, operation_code, operation_version, category, project_id, subject_ref,"
        " params_sha256, units, estimated_credits, reserved_credits, funding_source, sponsorship_id, state, idempotency_key,"
        " estimated_cost_cents, cost_status, provider, model, request_id)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'created',$14,$15,$16,$17,$18,$19) RETURNING *",
        ctx.org_id, ctx.user_id, op["code"], op["version"], op["category"], project_id, subject_ref,
        params_hash(params), units, credits, credits if fs in ("promotional", "purchased", "sponsorship") else 0, fs,
        pv.get("sponsorship", {}).get("id") if fs == "sponsorship" else None, idempotency_key,
        pv["estimated_cost_cents"], pv["cost_status"], ctx.app.ai.provider_name if op["provider_mode"] != "local" else "local",
        (ctx.app.settings.ai_model or None) if op["provider_mode"] != "local" else None, getattr(ctx, "request_id", None))
    conn.run("UPDATE ai_executions SET state = 'authorized' WHERE id = $1", row["id"])
    conn.run("UPDATE ai_executions SET state = 'reserved' WHERE id = $1", row["id"])
    ctx.audit(conn, "ai.execution_authorized", "ai_execution", row["id"],
              {"operation": op["code"], "credits": credits, "funding_source": fs, "units": units})
    return _row(conn.one("SELECT * FROM ai_executions WHERE id = $1", row["id"])) | {"preview": pv}


def start(conn, execution_id: str) -> None:
    conn.run("UPDATE ai_executions SET state = 'running' WHERE id = $1 AND state = 'reserved'", execution_id)


def succeed(conn, ctx, execution_id: str, *, result_type: str | None = None, result_id: str | None = None,
            meta: dict | None = None, partial: bool = False) -> dict:
    """SUCCEEDED cobra o reservado (e só ele); PARTIAL não cobra (política declarada na operação).
    O consumo vai ao razão com idempotência pela própria execução."""
    meta = meta or {}
    ex = conn.one("SELECT * FROM ai_executions WHERE id = $1", execution_id)
    if not ex:
        raise not_found("Execução de IA")
    charged, outcome = 0, "nothing_to_charge"
    if not partial and ex["reserved_credits"] > 0 and ex["funding_source"] in ("promotional", "purchased"):
        r = conn.one("SELECT * FROM ai_credit_consume_bucket($1, $2, $3, $4, $5)", ex["org_id"], ex["funding_source"],
                     ex["reserved_credits"], ex["id"], f"exec:{ex['id']}")
        charged, outcome = int(r["charged"]), r["outcome"]
        if outcome == "insufficient":
            # a reserva garantia o saldo; chegar aqui é inconsistência — registra como falha, não cobra
            conn.run("UPDATE ai_executions SET state = 'failed', error_code = 'credit_inconsistency' WHERE id = $1", ex["id"])
            raise ApiError(409, "ai_credit_inconsistency", "O saldo não cobre o reservado: execução marcada como falha, nada cobrado.")
    elif not partial and ex["funding_source"] == "sponsorship":
        charged = ex["reserved_credits"]
    cost_status = ex["cost_status"]
    actual = None
    if ex["funding_source"] != "cached" and meta.get("tokens_in") is not None and ex["provider"] not in (None, "local"):
        preco = conn.one("SELECT input_per_mtok_cents, output_per_mtok_cents FROM ai_price_table WHERE provider = $1 AND (model = $2 OR $2 IS NULL)"
                         " AND effective_from <= current_date AND (effective_until IS NULL OR effective_until >= current_date)"
                         " ORDER BY effective_from DESC LIMIT 1", ex["provider"], ex["model"])
        if preco:
            actual = round((meta.get("tokens_in") or 0) * preco["input_per_mtok_cents"] / 1_000_000
                           + (meta.get("tokens_out") or 0) * preco["output_per_mtok_cents"] / 1_000_000, 4)
            cost_status = "measured"
        else:
            cost_status = "no_price_table"
    elif ex["provider"] in (None, "local"):
        actual, cost_status = 0, "local_no_cost"
    conn.run("UPDATE ai_executions SET state = $2, charged_credits = $3, result_type = $4, result_id = $5,"
             " tokens_in = $6, tokens_out = $7, latency_ms = $8, prompt_version = $9, actual_cost_cents = $10, cost_status = $11,"
             " provider = coalesce($12, provider) WHERE id = $1",
             ex["id"], "partial" if partial else "succeeded", charged, result_type, result_id,
             meta.get("tokens_in"), meta.get("tokens_out"), meta.get("latency_ms"), meta.get("prompt_version"),
             actual, cost_status, meta.get("provider"))
    if cost_status in ("measured", "local_no_cost") or ex["funding_source"] == "cached":
        conn.run("UPDATE ai_executions SET state = 'reconciled' WHERE id = $1", ex["id"])
    ctx.audit(conn, "ai.execution_settled", "ai_execution", ex["id"],
              {"state": "partial" if partial else "succeeded", "charged_credits": charged, "outcome": outcome, "cost_status": cost_status})
    return _row(conn.one("SELECT * FROM ai_executions WHERE id = $1", ex["id"]))


def fail(conn, ctx, execution_id: str, error_code: str) -> dict:
    conn.run("UPDATE ai_executions SET state = 'failed', error_code = $2 WHERE id = $1 AND state IN ('created','authorized','reserved','running')",
             execution_id, error_code[:80])
    ctx.audit(conn, "ai.execution_failed", "ai_execution", execution_id, {"error_code": error_code[:80]}, status="failure")
    return _row(conn.one("SELECT * FROM ai_executions WHERE id = $1", execution_id))


def cancel(conn, ctx, execution_id: str) -> dict:
    ex = conn.one("SELECT * FROM ai_executions WHERE id = $1 AND org_id = $2", execution_id, ctx.org_id)
    if not ex:
        raise not_found("Execução de IA")
    if ex["state"] not in ("created", "authorized", "reserved"):
        raise unprocessable("Só é possível cancelar antes de a execução começar", {"state": ex["state"]}, code="ai_not_cancellable")
    conn.run("UPDATE ai_executions SET state = 'cancelled' WHERE id = $1", ex["id"])
    ctx.audit(conn, "ai.execution_cancelled", "ai_execution", ex["id"], {})
    return _row(conn.one("SELECT * FROM ai_executions WHERE id = $1", ex["id"]))


def _row(ex: dict) -> dict:
    out = {k: (str(v) if k in ("id", "org_id", "user_id", "project_id", "sponsorship_id") and v is not None else v) for k, v in ex.items()}
    out["funding_label"] = FUNDING_LABEL.get(ex["funding_source"], ex["funding_source"])
    if out.get("estimated_cost_cents") is not None:
        out["estimated_cost_cents"] = float(out["estimated_cost_cents"])
    if out.get("actual_cost_cents") is not None:
        out["actual_cost_cents"] = float(out["actual_cost_cents"])
    return out


class Run:
    """Contexto de execução de uma operação: autoriza antes, liquida depois, falha sem cobrar.

        with Run(conn, ctx, "assist.summarize_project", params=..., input_chars=n) as run:
            ...trabalho...
            run.ok(result_type=..., result_id=..., meta=...)
    """

    def __init__(self, conn, ctx, code: str, **kw):
        self.conn, self.ctx, self.code, self.kw = conn, ctx, code, kw
        self.execution: dict | None = None
        self.t0 = time.perf_counter()
        self.settled = False

    def __enter__(self):
        self.execution = authorize(self.conn, self.ctx, self.code, **self.kw)
        if not self.execution.get("idempotent_replay"):
            start(self.conn, self.execution["id"])
        return self

    def ok(self, *, result_type: str | None = None, result_id: str | None = None, meta: dict | None = None, partial: bool = False) -> dict:
        meta = dict(meta or {})
        meta.setdefault("latency_ms", int((time.perf_counter() - self.t0) * 1000))
        if self.execution.get("idempotent_replay"):
            self.settled = True
            return self.execution
        self.execution = succeed(self.conn, self.ctx, self.execution["id"], result_type=result_type, result_id=result_id, meta=meta, partial=partial)
        self.settled = True
        return self.execution

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None and self.execution and not self.settled and not self.execution.get("idempotent_replay"):
            # A transação da rota é revertida pela exceção: a execução some junto e NADA é cobrado — é o
            # comportamento certo (sem resultado, sem débito). O registro de falha só sobrevive quando o
            # chamador trata o erro e chama `fail()` dentro de uma transação que vai ser confirmada.
            with contextlib.suppress(Exception):
                fail(self.conn, self.ctx, self.execution["id"], getattr(exc, "code", None) or exc_type.__name__)
        return False
