"""Métricas de negócio da plataforma, com procedência.

O QUE NÃO EXISTIA

`mrr`, `arr`, `gmv`, `churn`, `burn`, `runway`, `ltv`, `cac`: zero ocorrências em todo o código. Os
termos apareciam apenas em documentação — `UNIT_ECONOMICS.md`, `24_MONTH_FINANCIAL_MODEL.md` — sem
nenhum endpoint, tabela ou tela que os calculasse.

A REGRA DESTE MÓDULO

Todo número vem com `source`, `calculation`, `period` e `as_of`. É a exigência do §58 do prompt
desta rodada, e ela não é formalidade: um painel que mostra "MRR R$ 185.430" sem dizer de onde o
número saiu produz reunião em que ninguém sabe se ele inclui o imposto, o simulado ou o anual
diluído. Quando o número tem procedência, a discussão é sobre o negócio.

GMV NUNCA SOMA COM RECEITA

GMV é o valor que passa pelo ecossistema; receita é o que fica com a plataforma. Somá-los
multiplicaria o tamanho aparente do negócio por um fator que não existe. Os dois saem em campos
separados e o módulo não oferece nenhuma função que os junte.

O QUE ESTE MÓDULO RECUSA FAZER

Devolver número onde não há dado. `churn`, `ltv` e `cac` exigem histórico de assinatura paga que a
plataforma ainda não tem — ela nunca cobrou. Eles saem com `available: false` e o motivo, em vez de
zero. Zero significaria "nenhum cliente saiu"; a verdade é "nenhum cliente entrou ainda".
"""
from __future__ import annotations


def _metric(value, *, source: str, calculation: str, period: str, available: bool = True,
            unavailable_reason: str | None = None, currency: str | None = "BRL") -> dict:
    d = {"value": value, "available": available, "source": source,
         "calculation": calculation, "period": period}
    if currency and value is not None:
        d["currency"] = currency
    if not available:
        d["unavailable_reason"] = unavailable_reason
        d["value"] = None
    return d


def recurring_revenue(c) -> dict:
    """MRR e ARR a partir das assinaturas ATIVAS, com o anual diluído em doze.

    Diluir o anual é o que torna o número comparável mês a mês. Somar o anual inteiro no mês do
    faturamento faria o MRR de janeiro parecer cinco vezes o de fevereiro — e alguém tomaria uma
    decisão com base nisso.
    """
    row = c.one(
        "SELECT coalesce(sum(CASE WHEN s.interval = 'year' THEN s.amount_cents / 12"
        "                         ELSE s.amount_cents END), 0) AS mrr_cents,"
        " count(*) AS subscriptions,"
        " count(*) FILTER (WHERE s.interval = 'year') AS annual"
        " FROM subscriptions s"
        " WHERE s.status = 'active' AND s.amount_cents IS NOT NULL"
        # Assinatura em sandbox não é receita. Incluí-la faria um ambiente de testes inflar o MRR.
        "   AND s.provider <> 'sandbox'")
    mrr = int(row["mrr_cents"] or 0)
    return {
        "mrr": _metric(mrr,
                       source="subscriptions (status=active, provider<>sandbox)",
                       calculation=("soma do valor mensal; assinatura anual dividida por 12;"
                                    " assinatura com provider=sandbox excluída"),
                       period="instantâneo"),
        "arr": _metric(mrr * 12,
                       source="mrr × 12",
                       calculation="MRR × 12; não é receita contratada, é a anualização do mês",
                       period="instantâneo"),
        "subscriptions": int(row["subscriptions"] or 0),
        "annual_subscriptions": int(row["annual"] or 0),
    }


def revenue_recognized(c, *, period) -> dict:
    """Receita de COMPETÊNCIA do mês, do plano de contas. Não é caixa."""
    row = c.one(
        "SELECT coalesce(sum(CASE WHEN a.side = 'credit' THEN a.amount_cents"
        "                         ELSE -a.amount_cents END), 0) AS cents"
        " FROM accounting_entries a JOIN chart_of_accounts coa ON coa.code = a.account_code"
        " WHERE a.period = date_trunc('month', $1::date)::date AND coa.nature = 'revenue'"
        "   AND coa.code NOT LIKE '4.9%'", period)
    deducoes = c.one(
        "SELECT coalesce(sum(CASE WHEN a.side = 'debit' THEN a.amount_cents"
        "                         ELSE -a.amount_cents END), 0) AS cents"
        " FROM accounting_entries a WHERE a.period = date_trunc('month', $1::date)::date"
        "   AND a.account_code LIKE '4.9%'", period)
    bruta, ded = int(row["cents"] or 0), int(deducoes["cents"] or 0)
    return {
        "gross_revenue": _metric(bruta, source="accounting_entries × chart_of_accounts (4.x)",
                                 calculation="créditos menos débitos nas contas de receita, "
                                             "excluindo deduções (4.9.x)",
                                 period=str(period)),
        "deductions": _metric(ded, source="accounting_entries (4.9.x)",
                              calculation="estornos, cancelamentos e tributos sobre a receita",
                              period=str(period)),
        "net_revenue": _metric(bruta - ded, source="receita bruta − deduções",
                               calculation="o número que entra no resultado", period=str(period)),
    }


def cash_flow(c, *, period) -> dict:
    """Caixa do mês: o que entrou e saiu de fato, por `cash_date`."""
    row = c.one(
        "SELECT coalesce(sum(CASE WHEN coa.nature = 'asset' AND a.side = 'debit'"
        "                         THEN a.amount_cents ELSE 0 END), 0) AS entradas,"
        " coalesce(sum(CASE WHEN coa.nature = 'asset' AND a.side = 'credit'"
        "                   THEN a.amount_cents ELSE 0 END), 0) AS saidas"
        " FROM accounting_entries a JOIN chart_of_accounts coa ON coa.code = a.account_code"
        " WHERE a.cash_date >= date_trunc('month', $1::date)::date"
        "   AND a.cash_date < (date_trunc('month', $1::date) + interval '1 month')::date"
        "   AND coa.code LIKE '1.1%'", period)
    entrou, saiu = int(row["entradas"] or 0), int(row["saidas"] or 0)
    return {
        "cash_in": _metric(entrou, source="accounting_entries por cash_date, contas 1.1.x",
                           calculation="débitos em disponibilidades", period=str(period)),
        "cash_out": _metric(saiu, source="accounting_entries por cash_date, contas 1.1.x",
                            calculation="créditos em disponibilidades", period=str(period)),
        "net_cash": _metric(entrou - saiu, source="entradas − saídas",
                            calculation="variação de caixa da competência pelo regime de CAIXA, "
                                        "distinta da receita de competência",
                            period=str(period)),
    }


def expenses(c, *, period) -> dict:
    """Despesa da plataforma do mês, por centro de custo e por conta."""
    total = c.scalar("SELECT coalesce(sum(amount_cents),0) FROM platform_expenses"
                     " WHERE period = date_trunc('month', $1::date)::date"
                     "   AND status <> 'cancelled'", period) or 0
    por_cc = [dict(r) for r in c.query(
        "SELECT cost_center, sum(amount_cents) AS cents FROM platform_expenses"
        " WHERE period = date_trunc('month', $1::date)::date AND status <> 'cancelled'"
        " GROUP BY cost_center ORDER BY sum(amount_cents) DESC", period)]
    por_conta = [dict(r) for r in c.query(
        "SELECT e.account_code, coa.name, sum(e.amount_cents) AS cents FROM platform_expenses e"
        " JOIN chart_of_accounts coa ON coa.code = e.account_code"
        " WHERE e.period = date_trunc('month', $1::date)::date AND e.status <> 'cancelled'"
        " GROUP BY e.account_code, coa.name ORDER BY sum(e.amount_cents) DESC", period)]
    # Custo de IA tem fonte própria e é a única despesa que a plataforma já media.
    ia = c.one("SELECT count(*) AS chamadas,"
               " count(*) FILTER (WHERE cost_status = 'no_price_table') AS sem_preco,"
               " coalesce(sum(cost_cents_estimate),0) AS cents FROM ai_usage"
               " WHERE created_at >= date_trunc('month', $1::date)"
               "   AND created_at < date_trunc('month', $1::date) + interval '1 month'", period)
    return {
        "total": _metric(int(total), source="platform_expenses (status<>cancelled)",
                         calculation="soma por competência", period=str(period)),
        "by_cost_center": por_cc,
        "by_account": por_conta,
        "ai_cost": _metric(
            int(ia["cents"] or 0), source="ai_usage × ai_price_table",
            calculation="soma de cost_cents_estimate",
            period=str(period),
            available=not (ia["chamadas"] and ia["sem_preco"] == ia["chamadas"]),
            unavailable_reason=("`ai_price_table` está vazia: toda chamada fica em "
                                "cost_status='no_price_table' e o custo é nulo — nunca zero, "
                                "porque zero mentiria")
            if (ia["chamadas"] and ia["sem_preco"] == ia["chamadas"]) else None),
        "ai_calls_without_price": int(ia["sem_preco"] or 0),
    }


def gmv(c, *, period) -> dict:
    """Valor que passa pelo ecossistema. NÃO é receita, e o módulo não oferece como somá-los.

    Receita da plataforma sobre esse GMV hoje é ZERO: a taxa de intermediação está declarada e
    inativa, recusada pelo banco (ADR-022).
    """
    aportes = c.one(
        "SELECT coalesce(sum(amount_cents),0) AS cents, count(*) AS n FROM commitments"
        " WHERE created_at >= date_trunc('month', $1::date)"
        "   AND created_at < date_trunc('month', $1::date) + interval '1 month'", period)
    return {
        "gmv": _metric(int(aportes["cents"] or 0), source="commitments",
                       calculation="soma dos aportes comprometidos no mês",
                       period=str(period)),
        "commitments": int(aportes["n"] or 0),
        "platform_revenue_on_gmv": _metric(
            0, source="monetization_rules.marketplace.take_rate",
            calculation="zero: a regra está inativa e o banco recusa ativá-la sem custódia",
            period=str(period)),
        "warning": "GMV NÃO é receita. Somá-los multiplicaria o tamanho aparente do negócio por um "
                   "fator que não existe.",
    }


def conversion(c) -> dict:
    """Conversão de gratuito para pago, e o que ainda não há como medir."""
    row = c.one(
        "SELECT (SELECT count(*) FROM organizations WHERE status = 'active') AS orgs,"
        " (SELECT count(*) FROM subscriptions WHERE status = 'active'"
        "    AND provider <> 'sandbox') AS pagas,"
        " (SELECT count(*) FROM free_periods WHERE status = 'active' AND ends_at > now()) AS gratuitas")
    orgs, pagas = int(row["orgs"] or 0), int(row["pagas"] or 0)
    return {
        "active_organizations": orgs,
        "paying": pagas,
        "in_free_period": int(row["gratuitas"] or 0),
        "free_to_paid": _metric(
            round(pagas * 100 / orgs, 2) if orgs else None, currency=None,
            source="subscriptions ativas ÷ organizações ativas",
            calculation="percentual de organizações com assinatura paga",
            period="instantâneo", available=bool(orgs)),
        "churn": _metric(
            None, currency=None, source="subscriptions",
            calculation="(cancelamentos no mês) ÷ (assinaturas ativas no início do mês)",
            period="mensal", available=False,
            unavailable_reason="Não há histórico de assinatura paga: a plataforma nunca cobrou. "
                               "Zero significaria 'nenhum cliente saiu'; a verdade é 'nenhum "
                               "cliente entrou ainda'."),
        "ltv": _metric(None, currency=None, source="—",
                       calculation="(receita média por cliente × margem bruta) ÷ churn",
                       period="—", available=False,
                       unavailable_reason="Depende de churn e de margem, e nenhum dos dois existe "
                                          "ainda. Ver UNIT_ECONOMICS.md §2."),
        "cac": _metric(None, currency=None, source="—",
                       calculation="gasto de marketing e vendas ÷ clientes novos",
                       period="—", available=False,
                       unavailable_reason="Exige despesa de marketing e vendas registrada em "
                                          "platform_expenses por pelo menos um mês."),
    }


def burn_and_runway(c, *, period) -> dict:
    """Queima de caixa e meses de autonomia.

    `runway` só existe quando a queima é POSITIVA. Com resultado positivo o conceito não se aplica,
    e devolver "infinito" seria um número que alguém colocaria num slide.
    """
    cx = cash_flow(c, period=period)
    desp = expenses(c, period=period)
    rec = revenue_recognized(c, period=period)
    liquido = (rec["net_revenue"]["value"] or 0) - (desp["total"]["value"] or 0)
    saldo = int(c.scalar(
        "SELECT coalesce(sum(CASE WHEN a.side = 'debit' THEN a.amount_cents"
        "                         ELSE -a.amount_cents END), 0)"
        " FROM accounting_entries a WHERE a.account_code LIKE '1.1%'") or 0)
    queima = -liquido
    return {
        "net_result": _metric(liquido, source="receita líquida − despesa da plataforma",
                              calculation="pelo regime de COMPETÊNCIA", period=str(period)),
        "cash_balance": _metric(saldo, source="accounting_entries, contas 1.1.x",
                                calculation="saldo acumulado de disponibilidades",
                                period="acumulado"),
        "burn": _metric(queima if queima > 0 else 0,
                        source="resultado negativo da competência",
                        calculation="despesa menos receita, quando positivo",
                        period=str(period)),
        "runway_months": _metric(
            round(saldo / queima, 1) if queima > 0 and saldo > 0 else None, currency=None,
            source="saldo de caixa ÷ queima mensal",
            calculation="meses de autonomia mantida a queima atual",
            period=str(period), available=queima > 0 and saldo > 0,
            unavailable_reason=("A queima não é positiva nesta competência: o conceito de autonomia "
                                "não se aplica." if queima <= 0 else
                                "Sem saldo de caixa lançado, não há autonomia a calcular.")),
        "cash_net": cx["net_cash"],
    }


def summary(c, *, period) -> dict:
    """O painel executivo. Todo número com procedência; nenhum número inventado."""
    from ..clock import now
    out = {
        "period": str(period),
        "as_of": now().isoformat(),
        "recurring": recurring_revenue(c),
        "revenue": revenue_recognized(c, period=period),
        "cash": cash_flow(c, period=period),
        "expenses": expenses(c, period=period),
        "gmv": gmv(c, period=period),
        "conversion": conversion(c),
        "result": burn_and_runway(c, period=period),
    }
    # Quantos números não têm resposta ainda. Dizer isso no topo é o que evita a leitura de que o
    # painel está completo e os valores são realmente zero.
    faltando = _count_unavailable(out)
    out["unavailable_metrics"] = faltando
    out["honesty_note"] = (
        f"{faltando} métrica(s) sem valor por falta de dado, não por serem zero. Cada uma diz o "
        "motivo em `unavailable_reason`.")
    return out


def _count_unavailable(obj) -> int:
    if isinstance(obj, dict):
        if "available" in obj and obj.get("available") is False:
            return 1
        return sum(_count_unavailable(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_count_unavailable(v) for v in obj)
    return 0
