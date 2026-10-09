#!/usr/bin/env python3
"""Modelo econômico de 120 meses — IMPACTO (análise, v0.30.0). NÃO altera regra, catálogo, plano nem banco.

    python3 scripts/analysis/economic_model_120m.py        # escreve docs/analysis/economia_v0300/ (xlsx, png, json, md)

O que é: um MODELO com premissas abertas, em três cenários, para DOIS desenhos que o Superprompt manda avaliar sem confundir:
  * ATUAL   — só o que o repositório já decidiu: taxa de serviço 3,50 % sobre operações QUITADAS (regra hoje inativa; o modelo tem um
              mês de ativação como premissa) + serviços/inteligência avulsos. Sem contrato recorrente.
  * HÍBRIDO — ATUAL + contratos institucionais anuais (software: governança, portfólio, auditoria, relatórios). ATENÇÃO: isto contraria a
              ADR-341 e a regra `saas.institutional.funder` está RECUSADA no catálogo. É PROPOSTA a decidir, não desenho vigente.

Cada premissa carrega a sua natureza: FATO (repositório) · HIPÓTESE DO PROPRIETÁRIO (já declarada no repositório) · PREMISSA DE
MERCADO (não verificada; editável) · DERIVADO (cálculo). A planilha tem as mesmas fórmulas, abertas; este script calcula os mesmos
números em Python e a conferência (LibreOffice recalculando a planilha) está registrada no relatório.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "analysis" / "economia_v0300"
H = 120
MARKS = (6, 12, 24, 48, 120)

# ----------------------------------------------------------------------------------------------------------------- premissas
# Cada linha: chave, rótulo, natureza, fonte, {cenário: valor}
FACTS = {
    "service_bps": ("Taxa de serviço (bps)", "FATO", "config/economic_model.json · monetization_rules (contract.platform_service_fee, INATIVA)", 350),
    "authorship_bps": ("Participação de autoria (bps) — NÃO é receita", "FATO", "config/economic_model.json · ADR-337", 150),
    "ai_pack_price_per_credit_cents": ("Preço por crédito de IA (centavos) — hipótese de teste", "HIPÓTESE DO PROPRIETÁRIO", "ai_credit_packs (pack.100 = R$ 10,00 / 100)", 10),
    "pix_fee_pct": ("Taxa de pagamento (PIX) %", "HIPÓTESE DO PROPRIETÁRIO", "config/ai_economics.json pix_fee_pct_hypothesis", 1.0),
    "tax_pct": ("Tributos sobre receita % (hipótese)", "HIPÓTESE DO PROPRIETÁRIO", "config/ai_economics.json tax_pct_hypothesis (não é parecer)", 8.65),
    "support_cents_user_month": ("Suporte por usuário ativo/mês (centavos)", "HIPÓTESE DO PROPRIETÁRIO", "config/ai_economics.json", 30),
    "ai_infra_cents_op": ("Infra de IA por operação (centavos, motor local)", "HIPÓTESE DO PROPRIETÁRIO", "config/ai_economics.json infra_cents_per_operation_hypothesis.local", 2),
}

SC = ("conservador", "base", "agressivo")
PREM = [
    # chave, rótulo, natureza, fonte, (cons, base, agr)
    ("new_funders_month", "Novos financiadores por mês (operacional)", "HIPÓTESE DO PROPRIETÁRIO", "config/economic_model.json new_funding_clients_per_month = 3 em todos os cenários", (3, 3, 3)),
    ("ops_per_funder_year", "Operações por financiador por ano", "HIPÓTESE DO PROPRIETÁRIO", "config/economic_model.json scenarios", (1, 2, 3)),
    ("avg_op_cents", "Ticket médio financiado (centavos)", "HIPÓTESE DO PROPRIETÁRIO", "config/economic_model.json scenarios", (5_000_000, 15_000_000, 50_000_000)),
    ("settled_share", "Fração das operações que chega à quitação", "HIPÓTESE DO PROPRIETÁRIO", "config/economic_model.json scenarios", (0.60, 0.75, 0.85)),
    ("months_to_settle", "Meses até quitar", "HIPÓTESE DO PROPRIETÁRIO", "config/economic_model.json scenarios", (6, 5, 4)),
    ("ramp_months", "Rampa de entrada do financiador (meses)", "HIPÓTESE DO PROPRIETÁRIO", "config/economic_model.json scenarios", (6, 4, 3)),
    ("funder_churn_annual", "Churn anual de financiadores (deixam de originar)", "PREMISSA DE MERCADO", "não há histórico; valor editável", (0.25, 0.15, 0.10)),
    ("fee_activation_month", "Mês de ativação da regra da taxa (parecer + carta verde)", "PREMISSA DE MERCADO", "hoje INATIVA; depende de parecer — BLOCKED_EXTERNAL", (13, 7, 4)),
    ("fee_default_pct", "Inadimplência da taxa cobrada %", "PREMISSA DE MERCADO", "sem histórico", (8.0, 4.0, 2.0)),
    ("receipt_lag_months", "Prazo de recebimento (meses) de qualquer fatura", "PREMISSA DE MERCADO", "sem histórico", (2, 1, 1)),
    # contratos institucionais (só no desenho HÍBRIDO)
    ("inst_new_month", "Novos contratos institucionais por mês (HÍBRIDO)", "PREMISSA DE MERCADO", "não verificada; ADR-341 recusa assinatura — proposta a decidir", (0.5, 1.0, 2.0)),
    ("inst_start_month", "Mês em que o primeiro contrato institucional pode ser assinado", "PREMISSA DE MERCADO", "validação comercial antes (roadmap)", (10, 7, 4)),
    ("inst_acv_cents", "Valor anual do contrato institucional (centavos)", "PREMISSA DE MERCADO", "ancorada nas faixas-hipótese do catálogo recusado (R$ 2–10 mil/mês funder; R$ 3–15 mil ESG; R$ 3–50 mil gov)", (36_000_00, 72_000_00, 120_000_00)),
    ("inst_setup_cents", "Implantação por contrato (centavos, uma vez)", "PREMISSA DE MERCADO", "implementation.setup 'em aberto' no catálogo", (10_000_00, 20_000_00, 30_000_00)),
    ("inst_churn_annual", "Churn anual de contratos institucionais", "PREMISSA DE MERCADO", "sem histórico", (0.20, 0.12, 0.08)),
    ("inst_cac_cents", "CAC por contrato institucional (centavos)", "PREMISSA DE MERCADO", "sem histórico", (15_000_00, 12_000_00, 10_000_00)),
    # serviços e inteligência
    ("osc_per_funder", "OSCs ativas atraídas por financiador ativo", "PREMISSA DE MERCADO", "sem histórico", (4, 8, 12)),
    ("services_cents_per_osc_month", "Serviços/IA por OSC ativa por mês (centavos) — créditos, prontidão, documentos", "PREMISSA DE MERCADO", "ancorada em R$ 29 / R$ 79 / pacotes (hipóteses do catálogo); baixa adoção", (150, 400, 800)),
    ("services_cents_per_funder_month", "Serviços/IA por financiador ativo por mês (centavos)", "PREMISSA DE MERCADO", "relatórios/IA avulsos", (2_000, 6_000, 12_000)),
    ("services_cogs_pct", "Custo direto dos serviços % (IA/provedor, horas)", "PREMISSA DE MERCADO", "AI_COST_MODEL.md: margem por operação depende de provedor", (45.0, 35.0, 30.0)),
    # custos fixos
    ("fte_base", "Equipe inicial (FTE)", "PREMISSA DE MERCADO", "sem folha hoje; editável", (3, 4, 6)),
    ("fte_cost_cents_month", "Custo por FTE/mês, encargos inclusos (centavos)", "PREMISSA DE MERCADO", "não verificada", (12_000_00, 15_000_00, 18_000_00)),
    ("clients_per_extra_fte", "Clientes (financiadores + contratos) por FTE adicional", "PREMISSA DE MERCADO", "não verificada", (15, 20, 25)),
    ("infra_fixed_cents_month", "Infra fixa/mês (hospedagem, banco gerenciado, monitoramento) (centavos)", "PREMISSA DE MERCADO", "sem fatura; editável", (3_000_00, 4_000_00, 6_000_00)),
    ("infra_var_cents_client_month", "Infra variável por cliente ativo/mês (centavos)", "PREMISSA DE MERCADO", "sem medição", (40_00, 50_00, 60_00)),
    ("marketing_cents_month", "Marketing/vendas fixo por mês (centavos)", "PREMISSA DE MERCADO", "editável", (2_000_00, 6_000_00, 15_000_00)),
    ("funder_cac_cents", "CAC por financiador (centavos)", "PREMISSA DE MERCADO", "sem histórico", (3_000_00, 2_500_00, 2_000_00)),
    ("admin_cents_month", "Despesas administrativas/mês (contabilidade, jurídico recorrente, seguros) (centavos)", "PREMISSA DE MERCADO", "editável", (3_000_00, 4_000_00, 5_000_00)),
    ("initial_cash_cents", "Caixa inicial (centavos)", "PREMISSA DE MERCADO", "não informado pelo proprietário — zero por padrão", (0, 0, 0)),
]
PREM_IDX = {k: i for i, (k, *_r) in enumerate(PREM)}

VALUATION = {
    # múltiplos: ancorados em fontes externas citadas no relatório (SEG 2Q26, Aventis 2025/2026, SaaS Capital 2025); por cenário
    "saas_multiple": ("Múltiplo sobre ARR de software (×)", "PREMISSA DE MERCADO", "SEG 2Q26: público mediana 3,2×; M&A privado mediana 4,0×, média 6,2×; SaaS Capital 4,8–5,3× (modelado)", (2.5, 4.0, 6.0)),
    "txn_multiple": ("Múltiplo sobre receita líquida transacional (×)", "PREMISSA DE MERCADO", "Aventis 2025: marketplaces públicos mediana EV/Receita 2,3×; média histórica 5,6×", (1.5, 2.3, 4.0)),
    "services_multiple": ("Múltiplo sobre receita de serviços (×)", "PREMISSA DE MERCADO", "receita não recorrente; desconto forte", (1.0, 1.5, 2.0)),
    "ebitda_multiple": ("Múltiplo EV/EBITDA (só quando EBITDA > 0, cruzamento)", "PREMISSA DE MERCADO", "Aventis 2025: marketplaces públicos mediana 18×; privado menor", (8.0, 12.0, 15.0)),
    "discount_pct": ("Desconto por concentração, risco regulatório, iliquidez e dependência do fundador %", "PREMISSA DE MERCADO", "julgamento; editável", (45.0, 35.0, 25.0)),
}
DILUTION = [  # (mês, participação do fundador após a rodada) — PREMISSA DE MERCADO
    (0, 1.00), (12, 0.85), (24, 0.70), (48, 0.55), (120, 0.45),
]
TARGETS_BRL = [(100_000_000_00, "R$ 100 milhões"), (500_000_000_00, "R$ 500 milhões"), (1_000_000_000_00, "R$ 1 bilhão")]
USD_BRL_HYP = 5.5   # PREMISSA DE MERCADO (câmbio não cotado): só para a meta em US$


def p(sc: str, key: str):
    return PREM[PREM_IDX[key]][4][SC.index(sc)]


def founder_share(m: int) -> float:
    share = 1.0
    for month, s in DILUTION:
        if m >= month:
            share = s
    return share


# ----------------------------------------------------------------------------------------------------------------- motor
def simulate(sc: str, hybrid: bool, override: dict | None = None) -> list[dict]:
    g = {k: p(sc, k) for k in PREM_IDX}
    g.update({k: v[3] for k, v in FACTS.items()})
    if override:
        g.update(override)
    rows = []
    funders = 0.0
    inst = 0.0
    cash = g["initial_cash_cents"]
    billed_hist: list[int] = []        # faturamento por mês (para recebimento com atraso)
    billed_contracts_hist: list[float] = []   # contratos faturados por mês (anuais: novos + renovações)
    gmv_fee_hist: list[tuple[int, bool]] = []   # (taxa registrada no mês, originada após ativação?)
    for m in range(1, H + 1):
        funders = funders * (1 - g["funder_churn_annual"] / 12) + g["new_funders_month"]
        ramp = min(1.0, m / g["ramp_months"])
        ops = funders * g["ops_per_funder_year"] / 12 * ramp
        gmv = ops * g["avg_op_cents"]
        fee_registered = round(gmv * g["service_bps"] / 10_000)
        authorship = round(gmv * g["authorship_bps"] / 10_000)
        fee_eligible = m >= g["fee_activation_month"]
        gmv_fee_hist.append((fee_registered, fee_eligible))
        lag = int(g["months_to_settle"])
        if m - 1 - lag >= 0:
            reg, elig = gmv_fee_hist[m - 1 - lag]
            gmv_settled = round(reg * 10_000 / g["service_bps"] * g["settled_share"]) if reg else 0
            fee_recognized = round(reg * g["settled_share"]) if elig else 0
        else:
            gmv_settled, fee_recognized = 0, 0
        # contratos institucionais (HÍBRIDO)
        inst_new = g["inst_new_month"] if (hybrid and m >= g["inst_start_month"]) else 0.0
        inst = inst * (1 - g["inst_churn_annual"] / 12) + inst_new if hybrid else 0.0
        mrr = round(inst * g["inst_acv_cents"] / 12)
        # contrato anual faturado na assinatura e RENOVADO a cada 12 meses pela coorte sobrevivente (faturado ≠ reconhecido)
        renew = billed_contracts_hist[m - 13] * (1 - g["inst_churn_annual"] / 12) ** 12 if m > 12 else 0.0
        billed_contracts = inst_new + renew
        billed_contracts_hist.append(billed_contracts)
        inst_billed = round(billed_contracts * g["inst_acv_cents"]) + round(inst_new * g["inst_setup_cents"])
        setup_recognized = round(inst_new * g["inst_setup_cents"])
        # serviços
        oscs = funders * g["osc_per_funder"]
        services = round(oscs * g["services_cents_per_osc_month"] + funders * g["services_cents_per_funder_month"])
        # receita reconhecida (regra: transacional só na quitação; software pro rata; serviços na entrega)
        revenue = fee_recognized + mrr + setup_recognized + services
        # faturamento e recebimento
        billed = fee_recognized + inst_billed + services
        billed_hist.append(billed)
        rl = int(g["receipt_lag_months"])
        received_gross = billed_hist[m - 1 - rl] if m - 1 - rl >= 0 else 0
        received = round(received_gross * (1 - g["fee_default_pct"] / 100))
        # custos
        clients = funders + inst
        fte = g["fte_base"] + clients / g["clients_per_extra_fte"]
        people = round(fte * g["fte_cost_cents_month"])
        infra = round(g["infra_fixed_cents_month"] + clients * g["infra_var_cents_client_month"])
        ai_cost = round(ops * g["ai_infra_cents_op"] + services * g["services_cogs_pct"] / 100)
        support = round((oscs + funders) * g["support_cents_user_month"])
        payment_fees = round(received * g["pix_fee_pct"] / 100)
        taxes = round(revenue * g["tax_pct"] / 100)
        cac = round(g["new_funders_month"] * g["funder_cac_cents"] + inst_new * g["inst_cac_cents"])
        marketing = g["marketing_cents_month"] + cac
        admin = g["admin_cents_month"]
        cogs = ai_cost + support + payment_fees + infra
        gross = revenue - cogs
        contribution = gross - taxes - cac
        ebitda = revenue - cogs - taxes - people - marketing - admin
        cash_flow = received - cogs - taxes - people - marketing - admin
        cash += cash_flow
        rows.append({
            "month": m, "funders": funders, "inst_contracts": inst, "inst_new": inst_new, "oscs": oscs, "ops": ops,
            "gmv_originated": round(gmv), "gmv_settled": gmv_settled, "authorship_cents": authorship,
            "fee_registered": fee_registered, "fee_recognized": fee_recognized, "mrr": mrr, "arr": mrr * 12,
            "setup_recognized": setup_recognized, "services": services, "revenue": revenue,
            "billed": billed, "billed_contracts": billed_contracts, "received": received, "cogs": cogs, "gross_margin": gross, "taxes": taxes, "people": people,
            "marketing": marketing, "cac": cac, "admin": admin, "contribution": contribution, "ebitda": ebitda,
            "cash_flow": cash_flow, "cash": cash, "fte": fte,
        })
    return rows


def milestones(rows: list[dict]) -> dict:
    out = {}
    for mk in MARKS:
        r = rows[mk - 1]
        trailing = rows[max(0, mk - 12):mk]
        out[mk] = {
            "funders": round(r["funders"], 1), "inst_contracts": round(r["inst_contracts"], 1), "mrr": r["mrr"], "arr": r["arr"],
            "revenue_month": r["revenue"], "revenue_ttm": sum(x["revenue"] for x in trailing),
            "fee_ttm": sum(x["fee_recognized"] for x in trailing), "services_ttm": sum(x["services"] for x in trailing),
            "software_ttm": sum(x["mrr"] + x["setup_recognized"] for x in trailing),
            "gmv_originated_ttm": sum(x["gmv_originated"] for x in trailing), "gmv_settled_ttm": sum(x["gmv_settled"] for x in trailing),
            "ebitda_ttm": sum(x["ebitda"] for x in trailing), "cash": r["cash"], "min_cash_to_date": min(x["cash"] for x in rows[:mk]),
            "revenue_cum": sum(x["revenue"] for x in rows[:mk]),
        }
    return out


def valuation(sc: str, ms: dict) -> dict:
    i = SC.index(sc)
    mult = {k: v[3][i] for k, v in VALUATION.items()}
    out = {}
    for mk, d in ms.items():
        ev_saas = d["arr"] * mult["saas_multiple"]
        ev_txn = d["fee_ttm"] * (1 - FACTS["tax_pct"][3] / 100) * mult["txn_multiple"]
        ev_srv = d["services_ttm"] * mult["services_multiple"]
        ev_sum = (ev_saas + ev_txn + ev_srv) * (1 - mult["discount_pct"] / 100)
        ev_ebitda = d["ebitda_ttm"] * mult["ebitda_multiple"] if d["ebitda_ttm"] > 0 else None
        share = founder_share(mk)
        out[mk] = {"ev_saas": round(ev_saas), "ev_txn": round(ev_txn), "ev_services": round(ev_srv), "discount_pct": mult["discount_pct"],
                   "ev": round(ev_sum), "ev_ebitda_cross": None if ev_ebitda is None else round(ev_ebitda), "founder_share": share,
                   "founder_equity": round(ev_sum * share),
                   "share_needed": {label: (t / ev_sum if ev_sum > 0 else None) for t, label in TARGETS_BRL}
                   | {"US$ 1 bilhão": (1_000_000_000 * USD_BRL_HYP * 100 / ev_sum if ev_sum > 0 else None)}}
    return out


def breakeven_month(rows: list[dict]) -> int | None:
    for r in rows:
        if r["ebitda"] > 0 and all(x["ebitda"] > 0 for x in rows[r["month"] - 1:min(H, r["month"] + 2)]):
            return r["month"]
    return None


def capital_need(rows: list[dict]) -> int:
    return -min(0, min(r["cash"] for r in rows))


# ----------------------------------------------------------------------------------------------------------------- saídas
def brl(c) -> str:
    v = round(c) / 100
    s = f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def write_xlsx(results: dict, path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.chart import LineChart, Reference
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Premissas"
    ws.append(["IMPACTO — modelo de 120 meses (análise v0.30.0). Edite as colunas C–E; tudo nas abas mensais recalcula. Nada aqui altera o produto."])
    ws.append(["Natureza: FATO = está no repositório · HIPÓTESE DO PROPRIETÁRIO = já declarada no repositório · PREMISSA DE MERCADO = não verificada, editável · DERIVADO = cálculo"])
    ws.append([])
    ws.append(["chave", "premissa", "Conservador", "Base", "Agressivo", "natureza", "fonte"])
    for c in ws[4]:
        c.font = Font(bold=True)
    row_of: dict[str, int] = {}
    for k, (label, nature, source, val) in FACTS.items():
        ws.append([k, label, val, val, val, nature, source]); row_of[k] = ws.max_row
    for k, label, nature, source, vals in PREM:
        ws.append([k, label, *vals, nature, source]); row_of[k] = ws.max_row
    ws.append([]); ws.append(["— VALUATION (premissas de mercado; fontes no relatório) —"])
    for k, (label, nature, source, vals) in VALUATION.items():
        ws.append([k, label, *vals, nature, source]); row_of[k] = ws.max_row
    ws.append(["usd_brl", "Câmbio US$/R$ (só para a meta em US$)", USD_BRL_HYP, USD_BRL_HYP, USD_BRL_HYP, "PREMISSA DE MERCADO", "não cotado"]); row_of["usd_brl"] = ws.max_row
    ws.append([]); ws.append(["— DILUIÇÃO DO FUNDADOR (mês, participação após a rodada) —"])
    for month, s in DILUTION:
        ws.append([f"dil_{month}", f"participação do fundador a partir do mês {month}", s, s, s, "PREMISSA DE MERCADO", "editável"]); row_of[f"dil_{month}"] = ws.max_row
    fill = PatternFill("solid", fgColor="FFF2CC")
    for r in range(5, ws.max_row + 1):
        for col in (3, 4, 5):
            ws.cell(r, col).fill = fill
    ws.column_dimensions["A"].width = 30; ws.column_dimensions["B"].width = 70; ws.column_dimensions["G"].width = 90

    def P(key: str, col: str) -> str:
        return f"Premissas!${col}${row_of[key]}"

    cols = ["Mês", "Financiadores ativos", "Contratos inst. ativos", "Novos contratos inst.", "OSCs ativas", "Operações", "GMV originado", "GMV quitado",
            "Participação de autoria (não é receita)", "Taxa registrada", "Taxa reconhecida (quitação, regra ativa)", "MRR software", "Implantação reconhecida",
            "Serviços", "RECEITA RECONHECIDA", "Faturado", "Recebido (após inadimplência)", "COGS", "Margem bruta", "Tributos", "Pessoal", "Marketing+CAC",
            "Admin", "Margem de contribuição", "EBITDA", "Fluxo de caixa", "Caixa acumulado", "FTE", "Contratos faturados no mês (novos + renovações anuais)"]
    for sc, col in zip(SC, ("C", "D", "E")):
        for design, hybrid in (("Atual", 0), ("Híbrido", 1)):
            sh = wb.create_sheet(f"{sc[:4].capitalize()}-{design}")
            sh.append([f"Cenário {sc} · desenho {design} (0 = sem contratos institucionais; 1 = com) · valores em CENTAVOS · fórmulas abertas"])
            sh.append(["hybrid", hybrid]); sh.append(cols)
            for c in sh[3]:
                c.font = Font(bold=True)
            first = 4
            for m in range(1, H + 1):
                r = first + m - 1
                prev = f"B{r - 1}" if m > 1 else "0"
                prev_inst = f"C{r - 1}" if m > 1 else "0"
                lag_row = f"OFFSET($A${first},A{r}-1-{P('months_to_settle', col)},0)"
                fee_lag = f"IF(A{r}-1-{P('months_to_settle', col)}>=0,OFFSET($J${first},A{r}-1-{P('months_to_settle', col)},0),0)"
                elig_lag = f"IF(A{r}-1-{P('months_to_settle', col)}>=0,OFFSET($A${first},A{r}-1-{P('months_to_settle', col)},0)>={P('fee_activation_month', col)},FALSE)"
                recv_lag = f"IF(A{r}-1-{P('receipt_lag_months', col)}>=0,OFFSET($P${first},A{r}-1-{P('receipt_lag_months', col)},0),0)"
                sh.append([
                    m,
                    f"={prev}*(1-{P('funder_churn_annual', col)}/12)+{P('new_funders_month', col)}",
                    f"=IF($B$2=1,{prev_inst}*(1-{P('inst_churn_annual', col)}/12)+D{r},0)",
                    f"=IF(AND($B$2=1,A{r}>={P('inst_start_month', col)}),{P('inst_new_month', col)},0)",
                    f"=B{r}*{P('osc_per_funder', col)}",
                    f"=B{r}*{P('ops_per_funder_year', col)}/12*MIN(1,A{r}/{P('ramp_months', col)})",
                    f"=F{r}*{P('avg_op_cents', col)}",
                    f"=IF({fee_lag}>0,ROUND({fee_lag}*10000/{P('service_bps', col)}*{P('settled_share', col)},0),0)",
                    f"=ROUND(G{r}*{P('authorship_bps', col)}/10000,0)",
                    f"=ROUND(G{r}*{P('service_bps', col)}/10000,0)",
                    f"=IF({elig_lag},ROUND({fee_lag}*{P('settled_share', col)},0),0)",
                    f"=ROUND(C{r}*{P('inst_acv_cents', col)}/12,0)",
                    f"=ROUND(D{r}*{P('inst_setup_cents', col)},0)",
                    f"=ROUND(E{r}*{P('services_cents_per_osc_month', col)}+B{r}*{P('services_cents_per_funder_month', col)},0)",
                    f"=K{r}+L{r}+M{r}+N{r}",
                    f"=K{r}+ROUND(AC{r}*{P('inst_acv_cents', col)},0)+M{r}+N{r}",
                    f"=ROUND({recv_lag}*(1-{P('fee_default_pct', col)}/100),0)",
                    f"=ROUND(F{r}*{P('ai_infra_cents_op', col)}+N{r}*{P('services_cogs_pct', col)}/100,0)+ROUND((E{r}+B{r})*{P('support_cents_user_month', col)},0)+ROUND(Q{r}*{P('pix_fee_pct', col)}/100,0)+ROUND({P('infra_fixed_cents_month', col)}+(B{r}+C{r})*{P('infra_var_cents_client_month', col)},0)",
                    f"=O{r}-R{r}",
                    f"=ROUND(O{r}*{P('tax_pct', col)}/100,0)",
                    f"=ROUND(AB{r}*{P('fte_cost_cents_month', col)},0)",
                    f"={P('marketing_cents_month', col)}+ROUND({P('new_funders_month', col)}*{P('funder_cac_cents', col)}+D{r}*{P('inst_cac_cents', col)},0)",
                    f"={P('admin_cents_month', col)}",
                    f"=S{r}-T{r}-ROUND({P('new_funders_month', col)}*{P('funder_cac_cents', col)}+D{r}*{P('inst_cac_cents', col)},0)",
                    f"=O{r}-R{r}-T{r}-U{r}-V{r}-W{r}",
                    f"=Q{r}-R{r}-T{r}-U{r}-V{r}-W{r}",
                    (f"=AA{r - 1}+Z{r}" if m > 1 else f"={P('initial_cash_cents', col)}+Z{r}"),
                    f"={P('fte_base', col)}+(B{r}+C{r})/{P('clients_per_extra_fte', col)}",
                    (f"=D{r}+AC{r - 12}*(1-{P('inst_churn_annual', col)}/12)^12" if m > 12 else f"=D{r}"),
                ])
                _ = lag_row
            for i in range(1, len(cols) + 1):
                sh.column_dimensions[get_column_letter(i)].width = 16
            ch = LineChart(); ch.title = f"{sc} · {design}: receita reconhecida × EBITDA × caixa (centavos)"; ch.height = 9; ch.width = 24
            for c_idx in (15, 25, 27):
                ch.add_data(Reference(sh, min_col=c_idx, min_row=3, max_row=first + H - 1), titles_from_data=True)
            ch.set_categories(Reference(sh, min_col=1, min_row=first, max_row=first + H - 1))
            sh.add_chart(ch, "AE4")
    # marcos (valores calculados em Python, conferidos contra a planilha recalculada no LibreOffice — ver relatório)
    mk = wb.create_sheet("Marcos")
    mk.append(["Marcos M6/M12/M24/M48/M120 — valores em R$ (calculados pelo mesmo motor em Python; a conferência com a planilha recalculada está no relatório)"])
    mk.append(["cenário", "desenho", "marco", "financiadores", "contratos inst.", "ARR software", "receita 12m", "taxa 12m", "software 12m", "serviços 12m",
               "GMV originado 12m", "GMV quitado 12m", "EBITDA 12m", "caixa", "mínimo de caixa até aqui", "EV (após desconto)", "patrimônio teórico do fundador"])
    for sc in SC:
        for design in ("atual", "hibrido"):
            ms = results[sc][design]["milestones"]; val = results[sc][design]["valuation"]
            for m in MARKS:
                d = ms[m]; v = val[m]
                mk.append([sc, design, f"M{m}", d["funders"], d["inst_contracts"], d["arr"] / 100, d["revenue_ttm"] / 100, d["fee_ttm"] / 100, d["software_ttm"] / 100,
                           d["services_ttm"] / 100, d["gmv_originated_ttm"] / 100, d["gmv_settled_ttm"] / 100, d["ebitda_ttm"] / 100, d["cash"] / 100,
                           d["min_cash_to_date"] / 100, v["ev"] / 100, v["founder_equity"] / 100])
    fx = wb.create_sheet("Fontes")
    fx.append(["Fontes externas usadas só para os múltiplos de valuation (datas e limites no relatório):"])
    fx.append(["Software Equity Group, SaaS Index 2Q26 — mediana EV/Receita TTM pública 3,2× (2Q25: 5,7×); M&A privado mediana 4,0×, média 6,2× (via peony.ink/blog/saas-valuation-multiples, lido em 09/10/2026)"])
    fx.append(["Aventis Advisors — SaaS Valuation Multiples 2015–2026 (abr/2026): M&A privado mediana Q1 2026 3,1×; mediana período 4,5× (quartis 2,4×/8,1×); negócios US$ 0–5M ≈ 3,3×"])
    fx.append(["SaaS Capital 2025 — múltiplo de ARR previsto (modelado, não observado): 4,8× bootstrapped / 5,3× com capital"])
    fx.append(["Aventis Advisors — Marketplace Valuation Multiples 2025 (S&P Capital IQ, mar/2025): público mediana EV/Receita 2,3×; média histórica 5,6×; EV/EBITDA mediana 18×"])
    fx.append(["Nenhuma dessas fontes é brasileira nem do terceiro setor; são âncoras, não comparáveis diretos. Nenhum múltiplo foi aplicado a GMV."])
    wb.save(path)


def write_charts(results: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    files = []
    months = list(range(1, H + 1))
    def M(v): return [x / 100 / 1000 for x in v]   # R$ mil
    # 1 receita mensal por fonte (Base, híbrido e atual)
    for design in ("atual", "hibrido"):
        rows = results["base"][design]["rows"]
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.stackplot(months, M([r["fee_recognized"] for r in rows]), M([r["mrr"] + r["setup_recognized"] for r in rows]), M([r["services"] for r in rows]),
                     labels=["Taxa de serviço (quitação)", "Software (contratos inst.)", "Serviços/IA"])
        ax.set_title(f"1. Receita reconhecida por fonte — cenário Base, desenho {design.upper()} (R$ mil/mês) — SIMULAÇÃO sobre premissas")
        ax.set_xlabel("mês"); ax.set_ylabel("R$ mil"); ax.legend(loc="upper left"); ax.grid(alpha=.3)
        f = OUT / f"g1_receita_por_fonte_{design}.png"; fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig); files.append(f.name)
    # 2 receita acumulada 3 cenários (híbrido vs atual)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for sc in SC:
        for design, ls in (("atual", "--"), ("hibrido", "-")):
            rows = results[sc][design]["rows"]; cum = []; s = 0
            for r in rows: s += r["revenue"]; cum.append(s)
            ax.plot(months, M(cum), ls, label=f"{sc} · {design}")
    ax.set_title("2. Receita reconhecida acumulada (R$ mil) — 3 cenários × 2 desenhos"); ax.grid(alpha=.3); ax.legend(); ax.set_xlabel("mês")
    f = OUT / "g2_receita_acumulada.png"; fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig); files.append(f.name)
    # 3 MRR/ARR híbrido
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for sc in SC:
        ax.plot(months, M([r["arr"] for r in results[sc]["hibrido"]["rows"]]), label=f"ARR software · {sc}")
    ax.set_title("3. ARR de software — desenho HÍBRIDO (R$ mil) — contraria ADR-341; proposta a decidir"); ax.grid(alpha=.3); ax.legend(); ax.set_xlabel("mês")
    f = OUT / "g3_mrr_arr.png"; fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig); files.append(f.name)
    # 4 GMV vs receita (base atual)
    rows = results["base"]["atual"]["rows"]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(months, [r["gmv_originated"] / 100 / 1e6 for r in rows], label="GMV originado (R$ mi) — NÃO é receita")
    ax.plot(months, [r["gmv_settled"] / 100 / 1e6 for r in rows], label="GMV quitado (R$ mi)")
    ax2 = ax.twinx(); ax2.plot(months, M([r["revenue"] for r in rows]), "k-", label="Receita da plataforma (R$ mil, eixo direito)")
    ax.set_title("4. GMV × receita da plataforma — cenário Base, desenho ATUAL"); ax.grid(alpha=.3); ax.legend(loc="upper left"); ax2.legend(loc="lower right"); ax.set_xlabel("mês")
    f = OUT / "g4_gmv_vs_receita.png"; fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig); files.append(f.name)
    # 5 EBITDA e margem
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for sc in SC:
        for design, ls in (("atual", "--"), ("hibrido", "-")):
            ax.plot(months, M([r["ebitda"] for r in results[sc][design]["rows"]]), ls, label=f"EBITDA · {sc} · {design}")
    ax.axhline(0, color="k", lw=.8); ax.set_title("5. EBITDA mensal (R$ mil)"); ax.grid(alpha=.3); ax.legend(fontsize=8); ax.set_xlabel("mês")
    f = OUT / "g5_ebitda.png"; fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig); files.append(f.name)
    # 6 clientes
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for sc in SC:
        ax.plot(months, [r["funders"] for r in results[sc]["atual"]["rows"]], "--", label=f"financiadores ativos · {sc}")
        ax.plot(months, [r["inst_contracts"] for r in results[sc]["hibrido"]["rows"]], "-", label=f"contratos institucionais · {sc} (híbrido)")
    ax.set_title("6. Clientes ativos"); ax.grid(alpha=.3); ax.legend(fontsize=8); ax.set_xlabel("mês")
    f = OUT / "g6_clientes.png"; fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig); files.append(f.name)
    # 7 caixa
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for sc in SC:
        for design, ls in (("atual", "--"), ("hibrido", "-")):
            ax.plot(months, M([r["cash"] for r in results[sc][design]["rows"]]), ls, label=f"caixa · {sc} · {design}")
    ax.axhline(0, color="k", lw=.8); ax.set_title("7. Caixa acumulado (R$ mil) — o ponto mais baixo é a necessidade de capital"); ax.grid(alpha=.3); ax.legend(fontsize=8); ax.set_xlabel("mês")
    f = OUT / "g7_caixa.png"; fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig); files.append(f.name)
    # 8 comparação cenários em marcos (receita 12m)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    w = 0.13; xs = range(len(MARKS))
    for i, sc in enumerate(SC):
        for j, design in enumerate(("atual", "hibrido")):
            vals = [results[sc][design]["milestones"][m]["revenue_ttm"] / 100 / 1000 for m in MARKS]
            ax.bar([x + (i * 2 + j) * w for x in xs], vals, w, label=f"{sc} · {design}")
    ax.set_xticks([x + 2.5 * w for x in xs]); ax.set_xticklabels([f"M{m}" for m in MARKS]); ax.set_title("8. Receita dos 12 meses anteriores a cada marco (R$ mil)"); ax.legend(fontsize=8); ax.grid(alpha=.3, axis="y")
    f = OUT / "g8_cenarios_marcos.png"; fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig); files.append(f.name)
    # 9 sensibilidade (tornado) sobre receita 120m, base híbrido
    sens = results["sensibilidade"]
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = list(sens.keys()); vals = [sens[k]["delta_revenue_120_pct"] for k in labels]
    ax.barh(labels, vals); ax.axvline(0, color="k", lw=.8); ax.set_title("9. Sensibilidade: variação da receita acumulada em 120 m (cenário Base, híbrido) — %")
    ax.grid(alpha=.3, axis="x")
    f = OUT / "g9_sensibilidade.png"; fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig); files.append(f.name)
    return files


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict = {}
    for sc in SC:
        results[sc] = {}
        for design, hybrid in (("atual", False), ("hibrido", True)):
            rows = simulate(sc, hybrid)
            ms = milestones(rows)
            results[sc][design] = {"rows": rows, "milestones": ms, "valuation": valuation(sc, ms), "breakeven_month": breakeven_month(rows),
                                   "capital_need_cents": capital_need(rows)}
    # sensibilidade e estresse (cenário Base, híbrido)
    base_rev = sum(r["revenue"] for r in results["base"]["hibrido"]["rows"])
    stress = {
        "crescimento 50 % menor (financiadores e contratos)": {"new_funders_month": 1.5, "inst_new_month": 0.5},
        "metade das operações por financiador": {"ops_per_funder_year": 1},
        "ticket médio financiado 50 % menor": {"avg_op_cents": 7_500_000},
        "quitação 3 meses mais lenta": {"months_to_settle": 8},
        "churn dobrado": {"funder_churn_annual": 0.30, "inst_churn_annual": 0.24},
        "CAC dobrado": {"funder_cac_cents": 5_000_00, "inst_cac_cents": 24_000_00},
        "pessoal e infra 30 % maiores": {"fte_cost_cents_month": 19_500_00, "infra_fixed_cents_month": 5_200_00},
        "inadimplência 15 %": {"fee_default_pct": 15.0},
        "ausência de contratos institucionais": {"inst_new_month": 0.0},
        "taxa transacional nunca ativada": {"fee_activation_month": 10_000},
        "concentração: 3 financiadores saem no mês 13 (churn 40 % no ano 2)": {"funder_churn_annual": 0.40},
    }
    sens = {}
    for label, ov in stress.items():
        rows = simulate("base", True, ov)
        rev = sum(r["revenue"] for r in rows)
        sens[label] = {"delta_revenue_120_pct": round((rev / base_rev - 1) * 100, 1), "capital_need_cents": capital_need(rows),
                       "breakeven_month": breakeven_month(rows), "cash_m120_cents": rows[-1]["cash"],
                       "ev_m48_cents": valuation("base", milestones(rows))[48]["ev"]}
    results["sensibilidade"] = sens
    write_xlsx(results, OUT / "IMPACTO_MODELO_120M.xlsx")
    charts = write_charts(results)
    summary = {sc: {d: {"milestones": results[sc][d]["milestones"], "valuation": results[sc][d]["valuation"], "breakeven_month": results[sc][d]["breakeven_month"],
                        "capital_need_cents": results[sc][d]["capital_need_cents"]} for d in ("atual", "hibrido")} for sc in SC}
    summary["sensibilidade"] = sens
    summary["premissas"] = {"fatos": {k: v[3] for k, v in FACTS.items()}, "por_cenario": {k: dict(zip(SC, vals)) for k, _l, _n, _s, vals in PREM},
                            "valuation": {k: dict(zip(SC, v[3])) for k, v in VALUATION.items()}, "diluicao": DILUTION, "usd_brl": USD_BRL_HYP}
    (OUT / "resultados_120m.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    for sc in SC:
        for d in ("atual", "hibrido"):
            r = results[sc][d]
            print(f"{sc:12} {d:8} receita 120m {brl(r['milestones'][120]['revenue_cum']):>18}  EBITDA 12m@M120 {brl(r['milestones'][120]['ebitda_ttm']):>16}  "
                  f"capital {brl(r['capital_need_cents']):>14}  break-even {r['breakeven_month']}  EV@M48 {brl(r['valuation'][48]['ev']):>16}")
    print("gráficos:", ", ".join(charts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
