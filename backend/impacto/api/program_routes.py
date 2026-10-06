"""Rotas do Programa e da análise que ele habilita (cadeia de resultado, lacuna territorial).

Três observações para quem revisar:

* ``GET /v1/programs/feed`` e ``GET /v1/programs/{id}`` de programa público são as rotas **sem sessão**
  desta camada. A proteção não vem de condição escrita na rota: vem de `programs_read` exigir
  `visibility = 'public' AND published_at IS NOT NULL AND status <> 'suspended'`, e de
  `programs.public_feed()` repetir o filtro num único lugar. Mesmo princípio de
  `marketplace.PUBLIC_STATES`.

* ``GET /v1/programs/{id}`` devolve **declarado** e **apurado** em objetos separados e nomeados. Isso é
  contrato, não apresentação: somar orçamento declarado com valor executado num número chamado
  "captado" é exatamente o que o invariante dos três estágios financeiros existe para impedir.

* ``GET /v1/territorial-gap`` é agregada e **não** devolve dado de pessoa. Devolve `needs_with_source`
  junto, para que lacuna apoiada em estimativa sem fonte não passe por fato.
"""
from __future__ import annotations

from ..economics import billable as BL
from ..economics import payments as PAY
from ..economics import programs as PG
from ..economics import value_ledger as VL
from ..http import Ctx, not_found, route
from . import economics_schemas as E

TP = ("programa",)
TG = ("territorio",)


# ================================================================================================ programa
@route("GET", "/v1/programs/status-graph", auth="user", tags=TP,
       summary="Transições possíveis de um programa, com quem move e se exige motivo")
def program_graph(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": PG.graph(c), "labels": PG.ST_LABEL, "roles": PG.ROLE_LABEL}


@route("GET", "/v1/programs/feed", auth="none", query=E.ProgramFeedQ, tags=TP,
       summary="Programas publicados (público, sem sessão)")
def program_feed(ctx: Ctx, q: E.ProgramFeedQ):
    with ctx.system_tx() as c:
        return PG.public_feed(c, territory=q.territory, cause=q.cause, limit=q.limit, offset=q.offset)


@route("GET", "/v1/programs", query=E.ProgramQ, min_role="viewer", tags=TP,
       summary="Programas da organização")
def program_list(ctx: Ctx, q: E.ProgramQ):
    with ctx.tx(readonly=True) as c:
        return PG.mine(c, org_id=ctx.org_id, status=q.status, limit=q.limit, offset=q.offset)


@route("POST", "/v1/programs", body=E.ProgramIn, min_role="manager", status=201, tags=TP,
       summary="Cria um programa (nasce em rascunho; o limite do plano é conferido aqui)")
def program_create(ctx: Ctx, body: E.ProgramIn):
    with ctx.tx() as c:
        # O limite `programs` do plano existia e era aplicado contra `calls` — o produto anunciava uma
        # entidade que não existia (SAAS_ECONOMIC_AUDIT.md §1 item 1). Agora é contado contra a coisa
        # certa.
        from ..services.entitlements import check_limit
        n = c.scalar("SELECT count(*) FROM programs WHERE owner_org_id = $1"
                     " AND status IN ('draft','open','in_execution','suspended')", ctx.org_id)
        check_limit(c, ctx, "programs", n)
        return PG.create(c, org_id=ctx.org_id, actor=ctx.user_id, **body.model_dump())


@route("GET", "/v1/programs/{program_id}", auth="none", tags=TP,
       summary="Um programa, com o declarado e o apurado em objetos separados")
def program_get(ctx: Ctx):
    pid = ctx.path["program_id"]
    # `ctx.org_id` LEVANTA 409 quando não há organização ativa, então a pergunta tem de ser feita no
    # principal. Perguntar por `ctx.org_id` aqui fazia um programa em rascunho responder
    # "selecione uma organização" a quem não tem sessão — o que é vazamento de existência.
    org = ctx.principal.org_id if ctx.principal else None
    if org:
        with ctx.tx(readonly=True) as c:
            return PG.get(c, program_id=pid, org_id=org)
    # Sem sessão: a política `programs_read` é quem decide, e ela só libera programa público publicado.
    # O filtro é repetido aqui de propósito — esta é uma rota sem sessão, e a redundância é barata.
    with ctx.system_tx() as c:
        row = c.one("SELECT 1 FROM programs WHERE id = $1 AND visibility = 'public'"
                    " AND published_at IS NOT NULL AND status <> 'suspended'", pid)
        if not row:
            raise not_found("Programa")
        return PG.get(c, program_id=pid, org_id=None)


@route("PATCH", "/v1/programs/{program_id}", body=E.ProgramPatch, min_role="manager", tags=TP,
       summary="Edita o que é declarado (situação e datas derivadas não passam por aqui)")
def program_patch(ctx: Ctx, body: E.ProgramPatch):
    with ctx.tx() as c:
        return PG.update(c, program_id=ctx.path["program_id"], org_id=ctx.org_id,
                         **body.model_dump(exclude_none=True))


@route("POST", "/v1/programs/{program_id}/transition", body=E.ProgramTransitionIn,
       min_role="manager", tags=TP,
       summary="Move a situação do programa (recusada se não estiver no grafo)")
def program_transition(ctx: Ctx, body: E.ProgramTransitionIn):
    with ctx.tx() as c:
        return PG.transition(c, program_id=ctx.path["program_id"], org_id=ctx.org_id,
                             actor=ctx.user_id, to_status=body.to_status, reason=body.reason)


# ---------------------------------------------------------------- o que o programa agrega
@route("POST", "/v1/programs/{program_id}/calls", body=E.ProgramCallIn, min_role="manager",
       status=201, tags=TP, summary="Pendura um edital da própria organização no programa")
def program_add_call(ctx: Ctx, body: E.ProgramCallIn):
    with ctx.tx() as c:
        return PG.add_call(c, program_id=ctx.path["program_id"], call_id=body.call_id,
                           org_id=ctx.org_id, actor=ctx.user_id)


@route("DELETE", "/v1/programs/{program_id}/calls/{call_id}", min_role="manager", tags=TP,
       summary="Desfaz o vínculo com o edital")
def program_del_call(ctx: Ctx):
    with ctx.tx() as c:
        return PG.remove_call(c, program_id=ctx.path["program_id"], call_id=ctx.path["call_id"],
                              org_id=ctx.org_id)


@route("POST", "/v1/programs/{program_id}/projects", body=E.ProgramProjectIn, min_role="manager",
       status=201, tags=TP,
       summary="Põe ou move um projeto no programa, com o papel que ele tem ali")
def program_set_project(ctx: Ctx, body: E.ProgramProjectIn):
    with ctx.tx() as c:
        return PG.set_project(c, program_id=ctx.path["program_id"], org_id=ctx.org_id,
                              actor=ctx.user_id, **body.model_dump())


@route("POST", "/v1/programs/{program_id}/indicators", body=E.ProgramIndicatorIn,
       min_role="manager", status=201, tags=TP,
       summary="Acrescenta indicador ao programa (linha de base exige fonte)")
def program_add_indicator(ctx: Ctx, body: E.ProgramIndicatorIn):
    with ctx.tx() as c:
        return PG.add_indicator(c, program_id=ctx.path["program_id"], org_id=ctx.org_id,
                                actor=ctx.user_id, **body.model_dump())


@route("POST", "/v1/programs/{program_id}/needs", body=E.ProgramNeedIn, min_role="manager",
       status=201, tags=TP,
       summary="Liga o programa a uma necessidade de território (habilita a análise de lacuna)")
def program_add_need(ctx: Ctx, body: E.ProgramNeedIn):
    with ctx.tx() as c:
        return PG.add_need(c, program_id=ctx.path["program_id"], need_id=body.need_id,
                           org_id=ctx.org_id, actor=ctx.user_id)


# ================================================================================================ análise
@route("GET", "/v1/projects/{project_id}/result-chain", min_role="viewer", tags=TP,
       summary="Cadeia de resultado do projeto, com a força declarada de cada elo")
def project_result_chain(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return PG.result_chain(c, project_id=ctx.path["project_id"])


@route("GET", "/v1/territorial-gap", query=E.GapQ, min_role="viewer", tags=TG,
       summary="Demanda registrada contra oferta, por território — agregado, sem dado de pessoa")
def territorial_gap(ctx: Ctx, q: E.GapQ):
    with ctx.tx(readonly=True) as c:
        return PG.territorial_gap(c, territory_prefix=q.territory_prefix)


# ================================================================================================ Value Ledger
@route("GET", "/v1/value/types", auth="user", tags=("valor",),
       summary="Vocabulário de eventos de valor, com a linha de referência vigente e a fonte dela")
def value_types(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        items = VL.types(c)
    return {"items": items,
            "note": ("`has_baseline=false` significa que ninguém declarou, com fonte, quanto trabalho "
                     "humano aquela unidade substitui — e então nenhuma estimativa de tempo é "
                     "produzida para eventos daquele tipo.")}


@route("GET", "/v1/value/summary", query=E.ValueSummaryQ, min_role="viewer", tags=("valor",),
       summary="Quanto valor o sistema criou para esta organização (contagem medida, tempo estimado)")
def value_summary(ctx: Ctx, q: E.ValueSummaryQ):
    from datetime import timedelta

    from ..clock import now as _now
    with ctx.tx(readonly=True) as c:
        return VL.summary(c, org_id=ctx.org_id, since=_now() - timedelta(days=q.days),
                          program_id=q.program_id)


@route("GET", "/v1/value/events", query=E.ValueFeedQ, min_role="viewer", tags=("valor",),
       summary="Os eventos de valor da organização, um a um")
def value_events(ctx: Ctx, q: E.ValueFeedQ):
    with ctx.tx(readonly=True) as c:
        return VL.feed(c, org_id=ctx.org_id, event_type=q.event_type, limit=q.limit, offset=q.offset)


@route("POST", "/v1/admin/value/baselines", body=E.BaselineIn, auth="admin", status=201,
       tags=("valor",),
       summary="Declara a linha de referência de um tipo de evento (cria versão; não reescreve)")
def value_set_baseline(ctx: Ctx, body: E.BaselineIn):
    with ctx.tx() as c:
        return VL.set_baseline(c, actor=ctx.user_id, **body.model_dump(exclude_none=True))


@route("POST", "/v1/admin/ai/prices", body=E.AiPriceIn, auth="admin", status=201, tags=("valor",),
       summary="Declara o preço de um modelo de IA (versionado, com fonte)")
def ai_set_price(ctx: Ctx, body: E.AiPriceIn):
    with ctx.tx() as c:
        return VL.set_ai_price(c, actor=ctx.user_id, **body.model_dump(exclude_none=True))


@route("GET", "/v1/admin/ai/cost", query=E.AiCostQ, auth="admin", tags=("valor",),
       summary="Custo estimado de IA por provedor, modelo e recurso — insumo da margem")
def ai_cost(ctx: Ctx, q: E.AiCostQ):
    with ctx.tx(readonly=True) as c:
        return VL.ai_cost_summary(c, org_id=q.org_id, days=q.days)


# ================================================================================================ monetização
@route("GET", "/v1/monetization/rules", auth="user", query=E.RulesQ, tags=("monetizacao",),
       summary="As regras de receita, em ordem de hierarquia, com o estado real e a carta legal")
def monetization_rules(ctx: Ctx, q: E.RulesQ):
    with ctx.tx(readonly=True) as c:
        return BL.rules(c, engine=q.engine)


@route("GET", "/v1/monetization/legal-cards", auth="user", tags=("monetizacao",),
       summary="Pesquisa de base normativa por receita (não é parecer jurídico)")
def monetization_legal_cards(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": BL.legal_cards(c),
                "note": ("Estas cartas registram PESQUISA de base normativa com fonte e data, e o grau "
                         "de certeza da pesquisa. Não substituem advogado nem contador, e nenhuma "
                         "afirma que uma estrutura é lícita.")}


@route("GET", "/v1/monetization/pipeline", min_role="viewer", query=E.PipelineQ, tags=("monetizacao",),
       summary="O que a plataforma criou de valor que alguma regra alcança — e por que não é cobrado")
def monetization_pipeline(ctx: Ctx, q: E.PipelineQ):
    with ctx.tx(readonly=True) as c:
        return BL.pipeline(c, org_id=ctx.org_id, status=q.status, limit=q.limit, offset=q.offset)


@route("POST", "/v1/admin/monetization/legal-cards", body=E.LegalCardIn, auth="admin", status=201,
       tags=("monetizacao",), summary="Registra a pesquisa de base normativa de uma receita")
def admin_add_legal_card(ctx: Ctx, body: E.LegalCardIn):
    with ctx.tx() as c:
        return BL.add_legal_card(c, actor=ctx.user_id, **body.model_dump(exclude_none=True))


@route("PATCH", "/v1/admin/monetization/rules/{rule_key}", body=E.RulePatch, auth="admin",
       tags=("monetizacao",),
       summary="Ajusta preço, situação jurídica e ativação de uma regra (o portão é no banco)")
def admin_set_rule(ctx: Ctx, body: E.RulePatch):
    with ctx.tx() as c:
        out = BL.set_rule(c, key=ctx.path["rule_key"], **body.model_dump(exclude_none=True))
        ctx.audit(c, "monetization.rule_changed", "monetization_rule", ctx.path["rule_key"],
                  body.model_dump(exclude_none=True), org_id=None)
    return out


@route("GET", "/v1/admin/monetization/pipeline", auth="admin", query=E.PipelineQ,
       tags=("monetizacao",), summary="A fila de monetização de todas as organizações")
def admin_pipeline(ctx: Ctx, q: E.PipelineQ):
    with ctx.tx(readonly=True) as c:
        return BL.pipeline(c, org_id=q.org_id, status=q.status, limit=q.limit, offset=q.offset)


# `billable_seq` e não `billable_id`: o roteador exige que TODO parâmetro de caminho terminado em
# `_id` seja um UUID (`http.py`, a guarda que devolve 404 para identificador malformado). O candidato a
# cobrança é sequencial, como o próprio `value_events`, então o nome do parâmetro respeita a convenção
# em vez de abrir exceção nela.
@route("POST", "/v1/admin/monetization/pipeline/{billable_seq}/waive", body=E.WaiveIn, auth="admin",
       tags=("monetizacao",), summary="Dispensa um candidato a cobrança, com motivo escrito")
def admin_waive(ctx: Ctx, body: E.WaiveIn):
    seq = ctx.path["billable_seq"]
    if not seq.isdigit():
        raise not_found("Candidato a cobrança")
    with ctx.tx() as c:
        out = BL.waive(c, billable_id=int(seq), reason=body.reason)
        ctx.audit(c, "monetization.waived", "billable", seq, {"reason": body.reason}, org_id=None)
    return out


# ================================================================================================ pagamento
@route("GET", "/v1/payments/status", auth="user", tags=("pagamento",),
       summary="O que está e o que não está configurado para cobrar de verdade")
def payments_status(ctx: Ctx):
    return PAY.status(ctx.settings)


@route("GET", "/v1/payments/state-graph", auth="user", tags=("pagamento",),
       summary="Transições possíveis de uma cobrança, com a origem de cada uma")
def payments_graph(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": PAY.graph(c), "labels": PAY.STATE_LABEL, "methods": PAY.METHOD_LABEL}


@route("GET", "/v1/payments/charges", query=E.ChargeQ, min_role="viewer", tags=("pagamento",),
       summary="As cobranças da organização, com o aviso em cada simulada")
def charges_list(ctx: Ctx, q: E.ChargeQ):
    with ctx.tx(readonly=True) as c:
        out = PAY.mine(c, org_id=ctx.org_id, state=q.state, limit=q.limit, offset=q.offset)
    return {**out, "provider_status": PAY.status(ctx.settings)}


@route("POST", "/v1/payments/charges", body=E.ChargeIn, min_role="owner", status=201,
       tags=("pagamento",), summary="Abre uma cobrança (nada é cobrado: é a intenção de cobrar)")
def charge_create(ctx: Ctx, body: E.ChargeIn):
    st = PAY.status(ctx.settings)
    with ctx.tx() as c:
        out = PAY.create(c, org_id=ctx.org_id, actor=ctx.user_id, provider=st["provider"],
                         kind=body.kind, method=body.method, amount_cents=body.amount_cents,
                         currency=body.currency, subscription_id=body.subscription_id,
                         invoice_id=body.invoice_id, billable_event_id=body.billable_event_seq,
                         installments=body.installments, instrument_id=body.instrument_id,
                         due_on=body.due_on)
    return {**out, "provider_status": st}


@route("GET", "/v1/payments/charges/{charge_id}", min_role="viewer", tags=("pagamento",),
       summary="Uma cobrança com a trilha inteira: por que ela está neste estado")
def charge_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        out = PAY.get(c, charge_id=ctx.path["charge_id"], org_id=ctx.org_id)
    return {**out, "provider_status": PAY.status(ctx.settings)}


@route("PUT", "/v1/payments/charges/{charge_id}/installments", body=E.InstallmentScheduleIn,
       min_role="owner", tags=("pagamento",),
       summary="Grava o cronograma do parcelamento (a soma tem de fechar com o total)")
def charge_installments(ctx: Ctx, body: E.InstallmentScheduleIn):
    with ctx.tx() as c:
        return PAY.set_installments(c, charge_id=ctx.path["charge_id"], org_id=ctx.org_id,
                                    schedule=[i.model_dump() for i in body.schedule])


@route("POST", "/v1/payments/charges/{charge_id}/transition", body=E.ChargeTransitionIn,
       min_role="owner", tags=("pagamento",),
       summary="Move a cobrança (recusada se não estiver no grafo)")
def charge_transition(ctx: Ctx, body: E.ChargeTransitionIn):
    with ctx.tx() as c:
        return PAY.transition(c, charge_id=ctx.path["charge_id"], org_id=ctx.org_id,
                              to_state=body.to_state, refunded_cents=body.refunded_cents,
                              failure_code=body.failure_code, failure_message=body.failure_message)


@route("GET", "/v1/admin/payments/revenue", query=E.RevenueQ, auth="admin", tags=("pagamento",),
       summary="Receita apurada, com o simulado em colunas próprias e nunca somado ao real")
def admin_revenue(ctx: Ctx, q: E.RevenueQ):
    from datetime import timedelta

    from ..clock import now as _now
    with ctx.tx(readonly=True) as c:
        out = PAY.revenue(c, since=_now() - timedelta(days=q.days),
                          provider_configured=PAY.status(ctx.settings)["configured"])
    return {**out, "provider_status": PAY.status(ctx.settings)}


@route("GET", "/v1/admin/payments/reconciliation", query=E.ReconciliationQ, auth="admin",
       tags=("pagamento",),
       summary="Onde o provedor e a plataforma discordam: cobrança parada e evento sem assinatura")
def admin_reconciliation(ctx: Ctx, q: E.ReconciliationQ):
    with ctx.tx(readonly=True) as c:
        return PAY.reconciliation(c, days=q.days)


# ================================================================================================ motores
@route("GET", "/v1/engines", auth="user", tags=("motores",),
       summary="Os motores operacionais: natureza, versão, o que produzem e o que nunca decidem")
def engines_registry(ctx: Ctx):
    from ..engines.registry import describe
    return describe()


@route("GET", "/v1/engines/coverage", auth="user", tags=("motores",),
       summary="Cobertura por motor: implementado, integrado, testado, E2E, segurança, "
               "observabilidade — tudo DERIVADO do código, nada declarado")
def engines_coverage(ctx: Ctx):
    """A tabela que diz onde a cadeia é forte e onde ela não é.

    Nenhuma das seis colunas é escrita: todas são derivadas do código, do roteador, da suíte de
    testes e do esquema. Um motor não ganha uma coluna sendo descrito como completo — ganha quando
    o fato existe. Por isso esta rota pode devolver `false`, e devolve: oito motores calculam e não
    deixam rastro durável, e isso aparece em vez de ficar escondido atrás de uma descrição boa.
    """
    from ..engines import coverage
    return coverage.table()
