"""Operação interna da plataforma: controladoria, financeiro, contabilidade, operações.

POR QUE ESTE ARQUIVO EXISTE

Duas lacunas que a auditoria desta rodada encontrou:

1. Não havia nenhum módulo de controladoria, contabilidade ou tesouraria DA PRÓPRIA PLATAFORMA. O
   "financeiro" era um punhado de rotas soltas sob `is_platform_admin`, sem papel dedicado.

2. 224 das 848 rotas (26,4%) não tinham tela nenhuma — incluindo `GET /v1/admin/ops/health`,
   `GET /v1/admin/payments/revenue`, `GET /v1/admin/jobs` e o Integration Hub inteiro. Construído,
   funcionando, invisível. Funcionalidade permitida e invisível é funcionalidade que não existe
   para quem usa.

A REGRA QUE GOVERNA O CONTEÚDO

`NON_CUSTODIAL_ARCHITECTURE.md` (ADR-284): estes painéis mostram e instruem; não movem dinheiro de
terceiros. Tesouraria aqui é patrimônio PRÓPRIO; instrução de pagamento é documento.
"""
from __future__ import annotations

from ..core import access as ACCESS
from ..db.pool import DbContext
from ..economics import approvals as AP
from ..economics import engine as ENG
from ..economics import metrics as MET
from ..http import ApiError, Ctx, route
from . import schemas as S

T = ("interno",)


def _sys(ctx: Ctx, readonly: bool = True):
    """Contexto de sistema. Estes painéis leem a operação da PLATAFORMA — não há organização
    cliente a que a RLS pudesse restringir, e restringir ao `platform` escondería o próprio dado
    que o painel existe para mostrar. A porta é a permissão declarada na rota."""
    return ctx.pool.tx(DbContext(system=True), readonly=readonly) if readonly else \
        ctx.pool.tx(DbContext(system=True))


def _period(valor: str | None):
    """Competência a partir de `AAAA-MM` ou `AAAA-MM-DD`.

    Levanta 422 em vez de 500: `?period=abacaxi` e `?period=2026-13` devolviam erro interno, com
    trace completo em `error_events` e contagem de 5xx na telemetria, por um parâmetro de URL que
    qualquer pessoa pode digitar errado.
    """
    from ..clock import today
    if not valor:
        return today().replace(day=1)
    from datetime import date as _d
    try:
        p = valor if len(valor) > 7 else valor + "-01"
        return _d.fromisoformat(p).replace(day=1)
    except ValueError:
        raise ApiError(422, "invalid_period",
                       "Competência inválida: use AAAA-MM (ex.: 2026-10).",
                       {"received": valor[:40]}) from None


def _inteiro(nome: str, valor: str | None, *, padrao: int, minimo: int, maximo: int) -> int:
    """Inteiro de parâmetro de consulta, com faixa. Também era 500, e também aceitava negativo.

    `?days=-5` respondia 200 e virava `now() - interval '-5 days'` — janela no FUTURO, em que as
    conferências vinham vazias e a contagem de divergências ficava subcontada. Um relatório de
    conciliação que responde "nenhuma divergência" por causa do sinal de um parâmetro é pior do que
    um erro.
    """
    if valor is None or valor == "":
        return padrao
    try:
        n = int(valor)
    except ValueError:
        raise ApiError(422, "invalid_number", f"`{nome}` precisa ser um número inteiro.",
                       {"parameter": nome, "received": str(valor)[:40]}) from None
    if not (minimo <= n <= maximo):
        raise ApiError(422, "out_of_range",
                       f"`{nome}` precisa estar entre {minimo} e {maximo}.",
                       {"parameter": nome, "received": n, "min": minimo, "max": maximo})
    return n


# ------------------------------------------------------------------------------------------------
# CONTROLADORIA — o painel executivo
# ------------------------------------------------------------------------------------------------

@route("GET", "/v1/controladoria/summary", auth="admin", permission="metrics.read", tags=T,
       summary="Painel executivo: MRR, ARR, receita, caixa, despesa, GMV, resultado e autonomia")
def controladoria(ctx: Ctx):
    p = _period(ctx.request.query_params.get("period"))
    with _sys(ctx) as c:
        resumo = MET.summary(c, period=p)
        resumo["pending_approvals"] = len(AP.pending(c, limit=200))
        resumo["divergences"] = ENG.reconcile(c, days=30)["divergences"]
    return resumo


@route("GET", "/v1/controladoria/reconciliation", auth="admin", permission="finance.read", tags=T,
       summary="Conciliação: o que foi esperado × o que aconteceu. APONTA, não corrige")
def reconciliation(ctx: Ctx):
    dias = _inteiro("days", ctx.request.query_params.get("days"),
                    padrao=30, minimo=1, maximo=180)
    with _sys(ctx) as c:
        return ENG.reconcile(c, days=dias)


# ------------------------------------------------------------------------------------------------
# FINANCEIRO — recebível, pagável, instrução
# ------------------------------------------------------------------------------------------------

@route("GET", "/v1/financeiro/summary", auth="admin", permission="finance.read", tags=T,
       summary="Recebível, pagável, instruções em aberto e gasto por centro de custo")
def financeiro(ctx: Ctx):
    p = _period(ctx.request.query_params.get("period"))
    with _sys(ctx) as c:
        receber = c.one("SELECT coalesce(sum(amount_cents),0) AS cents, count(*) AS n"
                        " FROM invoices WHERE status = 'open'")
        pagar = c.one("SELECT coalesce(sum(amount_cents),0) AS cents, count(*) AS n"
                      " FROM platform_expenses WHERE status IN ('approved','scheduled')")
        vencido = c.one("SELECT coalesce(sum(amount_cents),0) AS cents, count(*) AS n"
                        " FROM platform_expenses WHERE status IN ('approved','scheduled')"
                        "   AND due_on < current_date")
        instrucoes = [dict(r) for r in c.query(
            "SELECT id::text AS id, kind, payee_name, amount_cents, due_on, state"
            " FROM payment_instructions WHERE state NOT IN ('executed','reconciled','cancelled',"
            " 'rejected') ORDER BY due_on LIMIT 100")]
        desp = MET.expenses(c, period=p)
        cx = MET.cash_flow(c, period=p)
    return {"period": str(p),
            "receivable": {"cents": int(receber["cents"]), "count": int(receber["n"])},
            "payable": {"cents": int(pagar["cents"]), "count": int(pagar["n"])},
            "overdue": {"cents": int(vencido["cents"]), "count": int(vencido["n"])},
            "open_instructions": instrucoes,
            "expenses": desp, "cash": cx,
            "note": "A plataforma NÃO executa pagamento nem guarda valor de terceiro: emite "
                    "instrução e registra a evidência (ADR-284)."}


@route("POST", "/v1/financeiro/expenses", auth="admin", permission="finance.write",
       body=S.PlatformExpenseIn, status=201, tags=T,
       summary="Registra despesa da plataforma (quem registra não aprova)")
def create_expense(ctx: Ctx, body: S.PlatformExpenseIn):
    with _sys(ctx, readonly=False) as c:
        row = c.one(
            "INSERT INTO platform_expenses(period, account_code, cost_center, description,"
            " amount_cents, supplier_name, supplier_doc, due_on, document_ref, recurring,"
            " created_by) VALUES (date_trunc('month',$1::date)::date,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)"
            " RETURNING id::text, status, amount_cents",
            body.period, body.account_code, body.cost_center, body.description, body.amount_cents,
            body.supplier_name, body.supplier_doc, body.due_on, body.document_ref, body.recurring,
            ctx.user_id)
        ap = AP.request(c, operation="platform_expense", object_type="platform_expense",
                        object_id=row["id"], amount_cents=body.amount_cents,
                        summary=f"{body.cost_center}: {body.description}",
                        requested_by=ctx.user_id)
        ctx.audit(c, "internal.expense_registered", "platform_expense", row["id"],
                  {"amount_cents": body.amount_cents, "account": body.account_code,
                   "cost_center": body.cost_center})
    return {"id": row["id"], "status": row["status"], "approval": ap}


@route("GET", "/v1/financeiro/expenses", auth="admin", permission="finance.read", tags=T,
       summary="Despesas da plataforma por competência")
def list_expenses(ctx: Ctx):
    p = _period(ctx.request.query_params.get("period"))
    with _sys(ctx) as c:
        return {"period": str(p), "items": [dict(r) for r in c.query(
            "SELECT e.id::text AS id, e.period, e.account_code, coa.name AS account_name,"
            " e.cost_center, e.description, e.amount_cents, e.supplier_name, e.due_on, e.paid_on,"
            " e.status, e.recurring, e.approved_at, u.email AS created_by, a.email AS approved_by"
            " FROM platform_expenses e JOIN chart_of_accounts coa ON coa.code = e.account_code"
            " LEFT JOIN users u ON u.id = e.created_by LEFT JOIN users a ON a.id = e.approved_by"
            " WHERE e.period = $1 ORDER BY e.amount_cents DESC LIMIT 500", p)]}


# ------------------------------------------------------------------------------------------------
# INSTRUÇÃO DE PAGAMENTO — o "INSTRUI" do motor
# ------------------------------------------------------------------------------------------------

@route("GET", "/v1/financeiro/instructions", auth="admin", permission="instruction.read", tags=T,
       summary="Instruções de pagamento, por situação")
def list_instructions(ctx: Ctx):
    """A tela de instruções lia `/v1/financeiro/summary`, que exige `finance.read`.

    O menu a oferecia por `instruction.read` — uma permissão que NENHUMA rota declarava. Quem
    tivesse só ela via o item e levava 403. A auditoria desta versão encontrou cinco casos assim;
    este é o único que precisava de rota nova, porque a tela merece a sua própria leitura: ela
    mostra instrução, não resumo financeiro.
    """
    estados = ctx.request.query_params.get("state")
    with _sys(ctx) as c:
        itens = [dict(r) for r in c.query(
            "SELECT i.id::text AS id, i.kind, i.payee_name, i.payee_doc, i.amount_cents,"
            " i.currency, i.due_on, i.reference, i.state, i.account_code, i.cost_center,"
            " i.issued_at, i.executed_at, i.evidence_doc, i.cancel_reason,"
            " u.email AS created_by"
            " FROM payment_instructions i LEFT JOIN users u ON u.id = i.created_by"
            " WHERE ($1::text IS NULL OR i.state = ANY (string_to_array($1, ',')))"
            " ORDER BY i.due_on, i.created_at DESC LIMIT 300", estados)]
        por_estado = {r["state"]: int(r["n"]) for r in c.query(
            "SELECT state, count(*) AS n FROM payment_instructions GROUP BY state")}
    abertas = [i for i in itens if i["state"] not in
               ("executed", "reconciled", "cancelled", "rejected")]
    return {"items": itens, "open": abertas, "by_state": por_estado,
            "note": "Instrução é DOCUMENTO: a plataforma não executa a transferência e não guarda "
                    "valor de terceiro. A evidência é a prova de que quem paga pagou (ADR-284)."}


@route("POST", "/v1/financeiro/instructions", auth="admin", permission="instruction.create",
       body=S.InstructionIn, status=201, tags=T,
       summary="Emite instrução de pagamento (documento; a plataforma não executa o pagamento)")
def create_instruction(ctx: Ctx, body: S.InstructionIn):
    with _sys(ctx, readonly=False) as c:
        out = ENG.create_instruction(
            c, kind=body.kind, payee_name=body.payee_name, amount_cents=body.amount_cents,
            due_on=body.due_on, reference=body.reference, created_by=ctx.user_id,
            payee_doc=body.payee_doc, account_code=body.account_code,
            cost_center=body.cost_center, idempotency_key=body.idempotency_key)
        ctx.audit(c, "internal.instruction_created", "payment_instruction", out["id"],
                  {"amount_cents": body.amount_cents, "kind": body.kind,
                   "payee": body.payee_name})
    return out


@route("POST", "/v1/financeiro/instructions/{instruction_id}/issue", auth="admin",
       permission="instruction.approve", tags=T,
       summary="Emite a instrução aprovada — valor e destinatário congelam a partir daqui")
def issue_instruction(ctx: Ctx):
    with _sys(ctx, readonly=False) as c:
        out = ENG.issue_instruction(c, instruction_id=ctx.path["instruction_id"])
        ctx.audit(c, "internal.instruction_issued", "payment_instruction",
                  ctx.path["instruction_id"], {"amount_cents": out["amount_cents"]})
    return out


@route("POST", "/v1/financeiro/instructions/{instruction_id}/executed", auth="admin",
       permission="instruction.approve", body=S.ExecutionEvidenceIn, tags=T,
       summary="Registra que quem paga executou, com evidência (obrigatória)")
def record_execution(ctx: Ctx, body: S.ExecutionEvidenceIn):
    with _sys(ctx, readonly=False) as c:
        out = ENG.record_execution(c, instruction_id=ctx.path["instruction_id"],
                                   evidence_doc=body.evidence_doc)
        ctx.audit(c, "internal.instruction_executed", "payment_instruction",
                  ctx.path["instruction_id"], {"evidence": body.evidence_doc})
    return out


# ------------------------------------------------------------------------------------------------
# CONTABILIDADE — competência, lançamento, fechamento
# ------------------------------------------------------------------------------------------------

@route("GET", "/v1/contabilidade/summary", auth="admin", permission="accounting.read", tags=T,
       summary="Balancete da competência, plano de contas e situação do período")
def contabilidade(ctx: Ctx):
    p = _period(ctx.request.query_params.get("period"))
    with _sys(ctx) as c:
        periodo = c.one("SELECT period, status, closed_at FROM accounting_periods WHERE period = $1", p)
        # O SALDO sai daqui, não do navegador. A tela calculava `devedora ? d - c : c - d` com a
        # natureza lida da própria resposta: aritmética certa, procedência nenhuma — e a regra
        # desta rodada é que todo número apurado diz de onde veio.
        balancete = [dict(r) for r in c.query(
            "SELECT a.account_code, coa.name, coa.nature,"
            " sum(CASE WHEN a.side = 'debit' THEN a.amount_cents ELSE 0 END) AS debit_cents,"
            " sum(CASE WHEN a.side = 'credit' THEN a.amount_cents ELSE 0 END) AS credit_cents,"
            " CASE WHEN coa.nature IN ('asset','expense')"
            "      THEN sum(CASE WHEN a.side = 'debit' THEN a.amount_cents ELSE -a.amount_cents END)"
            "      ELSE sum(CASE WHEN a.side = 'credit' THEN a.amount_cents ELSE -a.amount_cents END)"
            " END AS balance_cents"
            " FROM accounting_entries a JOIN chart_of_accounts coa ON coa.code = a.account_code"
            " WHERE a.period = $1 GROUP BY a.account_code, coa.name, coa.nature"
            " ORDER BY a.account_code", p)]
        lotes = [dict(r) for r in c.query(
            "SELECT batch_id::text AS batch_id, count(*) AS entries,"
            " batch_is_balanced(batch_id) AS balanced FROM accounting_entries"
            " WHERE period = $1 GROUP BY batch_id ORDER BY min(created_at) DESC LIMIT 100", p)]
        rec = MET.revenue_recognized(c, period=p)
    debitos = sum(int(r["debit_cents"]) for r in balancete)
    creditos = sum(int(r["credit_cents"]) for r in balancete)
    return {
        "period": str(p),
        "status": periodo["status"] if periodo else "not_opened",
        "closed_at": periodo["closed_at"] if periodo else None,
        "trial_balance": balancete,
        "balance_note": "Saldo apurado no servidor: conta de natureza ativo ou despesa é devedora "
                        "(débito menos crédito); passivo, patrimônio líquido e receita são "
                        "credoras (crédito menos débito).",
        "totals": {"debit_cents": debitos, "credit_cents": creditos,
                   "balanced": debitos == creditos},
        "batches": lotes,
        "unbalanced_batches": [b["batch_id"] for b in lotes if not b["balanced"]],
        "revenue": rec,
        "note": "Competência, não caixa. O caixa está em /v1/financeiro/summary, e os dois números "
                "são diferentes de propósito.",
    }


@route("GET", "/v1/contabilidade/chart", auth="admin", permission="accounting.read", tags=T,
       summary="Plano de contas da plataforma")
def chart(ctx: Ctx):
    with _sys(ctx) as c:
        return {"accounts": [dict(r) for r in c.query(
            "SELECT code, name, nature, parent_code, analytical, active FROM chart_of_accounts"
            " ORDER BY code")],
            "cost_centers": [dict(r) for r in c.query(
                "SELECT code, name, active, owner_role FROM cost_centers ORDER BY code")]}


@route("POST", "/v1/contabilidade/batches", auth="admin", permission="accounting.write",
       body=S.AccountingBatchIn, status=201, tags=T,
       summary="Lança um lote (tem de fechar: débitos iguais a créditos)")
def post_batch(ctx: Ctx, body: S.AccountingBatchIn):
    # `source_kind` é fixado em `manual` aqui: este é o lançamento manual, e a origem de um
    # lançamento automático pertence a quem o gera, não a quem o envia.
    linhas = [{**e.model_dump(exclude_none=True), "source_kind": "manual"} for e in body.entries]
    with _sys(ctx, readonly=False) as c:
        for e in linhas:
            ENG.ensure_period(c, e["period"])
        lote = ENG.post_batch(c, entries=linhas, created_by=ctx.user_id)
        ctx.audit(c, "internal.accounting_batch", "accounting_batch", lote,
                  {"entries": len(body.entries)})
    return {"batch_id": lote, "entries": len(body.entries)}


@route("POST", "/v1/contabilidade/close", auth="admin", permission="accounting.close",
       body=S.ClosePeriodIn, tags=T,
       summary="Fecha a competência — irreversível; recusa se houver lote que não fecha")
def close_period(ctx: Ctx, body: S.ClosePeriodIn):
    p = _period(body.period)
    with _sys(ctx, readonly=False) as c:
        out = ENG.close_period(c, period=p, closed_by=ctx.user_id, note=body.note)
        ctx.audit(c, "internal.period_closed", "accounting_period", str(p),
                  {"note": body.note})
    return out


# ------------------------------------------------------------------------------------------------
# APROVAÇÃO — a alçada
# ------------------------------------------------------------------------------------------------

@route("GET", "/v1/aprovacoes", auth="admin", permission="finance.read", tags=T,
       summary="Pedidos de aprovação pendentes, com quantas faltam e quais permissões servem")
def pending_approvals(ctx: Ctx):
    with _sys(ctx) as c:
        itens = AP.pending(c)
        faixas = [dict(r) for r in c.query(
            "SELECT p.operation, r.min_cents, r.max_cents, r.approvals_needed,"
            " r.required_permissions FROM approval_rules r JOIN approval_policies p"
            " ON p.id = r.policy_id WHERE p.active ORDER BY p.operation, r.min_cents")]
    return {"items": itens, "bands": faixas,
            "note": "A alçada é DADO: mudar faixa é decisão de governança, não implantação."}


@route("POST", "/v1/aprovacoes/{request_id}/decide", auth="admin", permission="finance.approve",
       body=S.ApprovalDecisionIn, tags=T,
       summary="Decide um pedido. Quem pede não aprova, e faixas de duas exigem permissões diferentes")
def decide_approval(ctx: Ctx, body: S.ApprovalDecisionIn):
    ac = ACCESS.of(ctx)
    with _sys(ctx, readonly=False) as c:
        out = AP.decide(c, ac, request_id=ctx.path["request_id"], approve=body.approve,
                        permission_used=body.permission_used, note=body.note)
        ctx.audit(c, "internal.approval_decided", "approval_request", ctx.path["request_id"],
                  {"approve": body.approve, "permission_used": body.permission_used,
                   "state": out["state"]})
    return out


# ------------------------------------------------------------------------------------------------
# OPERAÇÕES — saúde, tarefas, integrações, alertas
# ------------------------------------------------------------------------------------------------

@route("GET", "/v1/operacoes/health", auth="admin", permission="health.read", tags=T,
       summary="HEALTH CENTER: banco, migrações, tarefas, backup, integrações e cobrança presa")
def health_center(ctx: Ctx):
    """Reúne numa resposta o que estava em três rotas sem tela nenhuma.

    `GET /v1/admin/ops/health`, `GET /v1/admin/jobs` e `GET /v1/admin/integrations/overview`
    existiam, respondiam bem e nenhuma tela as chamava. Um painel de saúde que ninguém abre não
    informa nada.
    """
    from ..economics import payments as PAY
    from ..ops import runs as RUNS
    with _sys(ctx) as c:
        migracoes = c.scalar("SELECT count(*) FROM schema_migrations")
        tarefas = [dict(r) for r in c.query(
            "SELECT job, status, started_at, finished_at, duration_ms, error"
            " FROM ops_job_runs ORDER BY id DESC LIMIT 50")]
        ultimas = [dict(r) for r in c.query(
            "SELECT DISTINCT ON (job) job, status, started_at, finished_at, duration_ms, error"
            " FROM ops_job_runs ORDER BY job, id DESC")]
        integracoes = [dict(r) for r in c.query(
            "SELECT key, name, category, maturity, active FROM integration_providers"
            " ORDER BY maturity, key")]
        presas = PAY.reconciliation(c, days=7)
        backup = RUNS.last(c, "backup")
        canario = RUNS.last(c, "email_canary")
    servicos = [
        {"name": "Banco de dados", "state": "ok", "detail": f"{migracoes} migrações aplicadas"},
        {"name": "Tarefas agendadas", "state": _job_state(ultimas),
         "detail": f"{len(ultimas)} tarefas com execução registrada"},
        {"name": "Backup", "state": _run_state(backup),
         "detail": _run_detail(backup, "nunca executou")},
        {"name": "Canário de e-mail", "state": _run_state(canario),
         "detail": _run_detail(canario, "nunca executou")},
        {"name": "Cobrança", "state": "warn" if presas.get("stuck_charges") else "ok",
         "detail": f"{len(presas.get('stuck_charges') or [])} cobrança(s) presa(s) há mais de 2 dias"},
        {"name": "Integrações", "state": "warn" if any(
            i["maturity"] == "scaffolded" for i in integracoes) else "ok",
         "detail": f"{sum(1 for i in integracoes if i['maturity'] == 'scaffolded')} em esqueleto"},
    ]
    return {"services": servicos, "jobs": ultimas, "ops_runs": tarefas,
            "integrations": integracoes, "charges": presas,
            "note": "Nenhum provedor está em produção; o backup local conferido NÃO é recuperação "
                    "de desastre sem cópia externa."}


def _job_state(ultimas: list[dict]) -> str:
    if not ultimas:
        return "unknown"
    return "fail" if any(j["status"] == "failed" for j in ultimas) else "ok"


def _run_state(run) -> str:
    if not run:
        return "unknown"
    return {"ok": "ok", "failed": "fail", "skipped": "warn",
            "not_configured": "warn"}.get(run.get("status"), "unknown")


def _run_detail(run, vazio: str) -> str:
    if not run:
        return vazio
    return f"{run.get('status')} em {run.get('finished_at') or run.get('started_at')}"


@route("GET", "/v1/operacoes/alerts", auth="admin", permission="health.read", tags=T,
       summary="CENTRAL DE ALERTAS: o que exige ação agora, por prioridade")
def alert_center(ctx: Ctx):
    """Alertas DERIVADOS do estado real. Não há tabela de alerta porque não há alerta sem causa:
    cada linha aqui aponta para o registro que a originou."""
    alertas: list[dict] = []
    from ..ops import runs as RUNS
    with _sys(ctx) as c:
        presas = c.query("SELECT id::text AS id, amount_cents, created_at FROM platform_charges"
                         " WHERE state IN ('checkout_started','pending','authorized')"
                         "   AND created_at < now() - interval '2 days' LIMIT 50")
        for r in presas:
            alertas.append({"priority": "HIGH", "kind": "charge_stuck",
                            "message": "Cobrança aberta há mais de dois dias",
                            "object_type": "platform_charge", "object_id": r["id"],
                            "at": r["created_at"]})
        vencidas = c.query("SELECT id::text AS id, payee_name, due_on FROM payment_instructions"
                           " WHERE state IN ('issued','approved') AND due_on < current_date LIMIT 50")
        for r in vencidas:
            alertas.append({"priority": "HIGH", "kind": "instruction_overdue",
                            "message": f"Instrução de pagamento vencida: {r['payee_name']}",
                            "object_type": "payment_instruction", "object_id": r["id"],
                            "at": r["due_on"]})
        pend = AP.pending(c, limit=50)
        for r in pend:
            alertas.append({"priority": "MEDIUM", "kind": "approval_pending",
                            "message": f"{r['operation']}: aguardando "
                                       f"{int(r['approvals_needed']) - int(r['approvals_given'])} "
                                       "aprovação(ões)",
                            "object_type": "approval_request", "object_id": r["id"],
                            "at": r["created_at"]})
        bk = RUNS.last(c, "backup")
        if not bk or bk.get("status") != "ok":
            alertas.append({"priority": "CRITICAL", "kind": "backup_missing",
                            "message": "Backup nunca concluiu com sucesso" if not bk
                                       else f"Último backup: {bk.get('status')}",
                            "object_type": "ops_job_run", "object_id": "backup", "at": None})
        sem_preco = c.scalar("SELECT count(*) FROM ai_usage WHERE cost_status = 'no_price_table'")
        if sem_preco:
            alertas.append({"priority": "MEDIUM", "kind": "ai_price_missing",
                            "message": f"{sem_preco} chamada(s) de IA sem preço declarado: "
                                       "`ai_price_table` está vazia e o custo fica nulo",
                            "object_type": "ai_price_table", "object_id": None, "at": None})
        rascunhos = c.scalar("SELECT count(*) FROM legal_documents WHERE status = 'draft'"
                             "   AND requires_acceptance")
        if rascunhos:
            alertas.append({"priority": "CRITICAL", "kind": "legal_draft",
                            "message": f"{rascunhos} minuta(s) que exigem aceite seguem em "
                                       "rascunho: nenhum aceite legal pode ser gravado",
                            "object_type": "legal_documents", "object_id": None, "at": None})
    ordem = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    alertas.sort(key=lambda a: ordem.get(a["priority"], 9))
    return {"items": alertas,
            "by_priority": {p: sum(1 for a in alertas if a["priority"] == p) for p in ordem},
            "note": "Alertas DERIVADOS do estado: cada um aponta o registro que o originou. Sem "
                    "tabela de alerta, não há alerta sem causa nem alerta que sobrevive à correção."}


# ------------------------------------------------------------------------------------------------
# ADMINISTRATIVO — tesouraria (patrimônio PRÓPRIO) e orçamento
# ------------------------------------------------------------------------------------------------

@route("GET", "/v1/tesouraria/summary", auth="admin", permission="treasury.read", tags=T,
       summary="Caixa e patrimônio PRÓPRIO da plataforma (nunca valor de terceiro)")
def tesouraria(ctx: Ctx):
    with _sys(ctx) as c:
        disponivel = int(c.scalar(
            "SELECT coalesce(sum(CASE WHEN side = 'debit' THEN amount_cents"
            "                         ELSE -amount_cents END), 0) FROM accounting_entries"
            " WHERE account_code = '1.1.1'") or 0)
        aplicado = int(c.scalar(
            "SELECT coalesce(sum(CASE WHEN side = 'debit' THEN amount_cents"
            "                         ELSE -amount_cents END), 0) FROM accounting_entries"
            " WHERE account_code = '1.1.2'") or 0)
        receber = int(c.scalar("SELECT coalesce(sum(amount_cents),0) FROM invoices"
                               " WHERE status = 'open'") or 0)
        pagar = int(c.scalar("SELECT coalesce(sum(amount_cents),0) FROM platform_expenses"
                             " WHERE status IN ('approved','scheduled')") or 0)
    return {
        "available_cents": disponivel, "invested_cents": aplicado,
        "receivable_cents": receber, "payable_cents": pagar,
        "net_position_cents": disponivel + aplicado + receber - pagar,
        "scope_note": "Patrimônio e caixa DA PLATAFORMA. A plataforma não custodia valor de "
                      "terceiro e não oferece investimento a cliente (ADR-284).",
    }


@route("GET", "/v1/administrativo/orcamento", auth="admin", permission="budget.read", tags=T,
       summary="Orçado × comprometido × realizado, por conta e centro de custo")
def budget(ctx: Ctx):
    from ..clock import today
    ano = _inteiro("year", ctx.request.query_params.get("year"),
                   padrao=today().year, minimo=2000, maximo=2100)
    with _sys(ctx) as c:
        orcamento = c.one("SELECT id::text AS id, version, status FROM platform_budgets"
                          " WHERE fiscal_year = $1 AND status = 'approved'", ano)
        if not orcamento:
            return {"year": ano, "approved_budget": None, "items": [],
                    "note": "Nenhum orçamento aprovado para este exercício. Orçado-vs-realizado "
                            "sem orçado é só realizado."}
        linhas = [dict(r) for r in c.query(
            "SELECT i.month, i.account_code, coa.name AS account_name, i.cost_center,"
            " i.amount_cents AS budgeted_cents,"
            " coalesce((SELECT sum(e.amount_cents) FROM platform_expenses e"
            "            WHERE e.account_code = i.account_code AND e.cost_center = i.cost_center"
            "              AND extract(month FROM e.period) = i.month"
            "              AND extract(year FROM e.period) = $2"
            "              AND e.status NOT IN ('cancelled')), 0) AS actual_cents"
            " FROM platform_budget_items i JOIN chart_of_accounts coa ON coa.code = i.account_code"
            " WHERE i.budget_id = $1 ORDER BY i.month, i.account_code", orcamento["id"], ano)]
    for linha in linhas:
        orc, real = int(linha["budgeted_cents"]), int(linha["actual_cents"])
        linha["variance_cents"] = orc - real
        linha["used_percent"] = round(real * 100 / orc, 1) if orc else None
    return {"year": ano, "approved_budget": orcamento, "items": linhas,
            "alerts": [linha for linha in linhas
                       if linha["used_percent"] is not None and linha["used_percent"] >= 80]}


@route("GET", "/v1/financeiro/fee-preview", auth="admin", permission="finance.read", tags=T,
       summary="CALCULA a taxa de marketplace sobre um valor — e diz que ela não é cobrável")
def fee_preview(ctx: Ctx):
    valor = _inteiro("amount_cents", ctx.request.query_params.get("amount_cents"),
                     padrao=0, minimo=1, maximo=10**12)
    with _sys(ctx) as c:
        return ENG.compute_marketplace_fee(c, contract_amount_cents=valor)
