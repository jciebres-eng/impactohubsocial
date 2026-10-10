#!/usr/bin/env python3
"""Modelo econômico de 24 meses do ECOSSISTEMA FINANCEIRO — IMPACTO v0.34.0 (análise; NÃO altera regra, catálogo nem banco).

    python3 scripts/analysis/financial_model_24m_v0340.py      # escreve docs/finance/modelo_24m/ (xlsx, png, json, md)

O que é: um modelo com premissas ABERTAS em três cenários (conservador, base, otimista) para as fontes de receita que o pacote
manda avaliar — doações comunitárias (taxa de serviço 1 %, hipótese), aportes institucionais (3,5 %, hipótese), taxa de serviço
do acordo (3,5 %, regra existente e INATIVA), serviços profissionais (10 % sobre contrato registrado — hipótese de teste do pacote,
recusada no catálogo), créditos de IA e licenças institucionais (hipótese contrária à ADR-341; aparece só como "a decidir").

NADA aqui é receita prevista: toda regra está INATIVA e nenhuma doação real existe. A política "gratuito até gerar valor" entra
no modelo como FRANQUIA (os primeiros R$ 20.000 liquidados/organização/ano não geram obrigação) e como ATRASO (aviso de 30 dias),
e a origem pública entra como ISENÇÃO (parcela do volume que nunca gera taxa). Cada premissa carrega a sua natureza.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "finance" / "modelo_24m"
H = 24
SC = ("conservador", "base", "otimista")

# ------------------------------------------------------------------------------------------------- premissas (natureza · fonte)
FACTS = {
    "donation_fee_bps": ("Taxa de serviço sobre doação (bps)", "FATO (regra INATIVA)", "fee_rule_versions donation.platform_fee v1", 100),
    "institutional_fee_bps": ("Taxa sobre aporte institucional (bps)", "FATO (regra INATIVA)", "fee_rule_versions donation.institutional_fee v1", 350),
    "contract_fee_bps": ("Taxa de serviço do acordo (bps)", "FATO (regra INATIVA)", "contract.platform_service_fee", 350),
    "allowance_cents": ("Franquia liquidada por organização/12 meses (centavos)", "FATO (política v1, hipótese)", "monetization_policy_versions free_until_value v1", 2_000_000),
    "notice_days": ("Aviso prévio (dias)", "FATO (política v1)", "monetization_policy_versions", 30),
    "ai_credit_price_cents": ("Preço por crédito de IA (centavos)", "HIPÓTESE DO PROPRIETÁRIO", "ai_credit_packs pack.100", 10),
}
PREM = [
    # chave, rótulo, natureza, fonte, {cenário: valor}
    ("orgs_m1", "Organizações ativas no mês 1", "PREMISSA DE MERCADO", "sem histórico; editar", {"conservador": 20, "base": 40, "otimista": 80}),
    ("orgs_growth", "Crescimento mensal de organizações ativas (%)", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 4.0, "base": 8.0, "otimista": 12.0}),
    ("campaigns_per_org", "Campanhas ativas por organização", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 0.3, "base": 0.5, "otimista": 0.8}),
    ("donors_per_campaign", "Doações confirmadas por campanha/mês", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 12, "base": 25, "otimista": 50}),
    ("ticket_cents", "Tíquete médio da doação (centavos)", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 4_000, "base": 6_000, "otimista": 8_000}),
    ("refund_pct", "Estornos/chargebacks sobre o bruto (%)", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 3.0, "base": 2.0, "otimista": 1.0}),
    ("public_share_pct", "Parcela do volume com recurso público (isento, %)", "PREMISSA DE MERCADO", "ADR-379", {"conservador": 40.0, "base": 30.0, "otimista": 20.0}),
    ("settle_lag_m", "Meses entre confirmação e liquidação", "PREMISSA DE MERCADO", "depende do provedor", {"conservador": 1, "base": 1, "otimista": 0}),
    ("inst_deals_m", "Aportes institucionais confirmados por mês (plataforma inteira)", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 0.5, "base": 1.0, "otimista": 2.0}),
    ("inst_ticket_cents", "Tíquete do aporte institucional (centavos)", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 2_000_000, "base": 5_000_000, "otimista": 10_000_000}),
    ("contracts_m", "Acordos de financiamento ativados por mês", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 0.5, "base": 1.0, "otimista": 2.0}),
    ("contract_gross_cents", "Valor médio do acordo (centavos)", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 5_000_000, "base": 10_000_000, "otimista": 20_000_000}),
    ("ai_ops_per_org", "Operações de IA pagas por organização/mês", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 5, "base": 15, "otimista": 30}),
    ("provider_pix_pct", "Tarifa do provedor sobre Pix (%)", "PREMISSA DE MERCADO", "tabela comercial, não lida (DONATIONS_PROVIDER_MATRIX)", {"conservador": 1.2, "base": 1.0, "otimista": 0.8}),
    ("provider_fixed_cents", "Tarifa fixa do provedor por transação (centavos)", "PREMISSA DE MERCADO", "idem", {"conservador": 50, "base": 30, "otimista": 0}),
    ("default_pct", "Inadimplência sobre as obrigações devidas (%)", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 15.0, "base": 8.0, "otimista": 4.0}),
    ("tax_pct", "Tributos sobre receita (%) — não é parecer", "HIPÓTESE DO PROPRIETÁRIO", "config/ai_economics.json", {"conservador": 8.65, "base": 8.65, "otimista": 8.65}),
    ("support_cents_org", "Suporte por organização ativa/mês (centavos)", "HIPÓTESE DO PROPRIETÁRIO", "config/ai_economics.json (escala)", {"conservador": 1_500, "base": 1_000, "otimista": 800}),
    ("infra_cents_m", "Infraestrutura fixa/mês (centavos)", "FATO APROXIMADO", "Railway Pro + Supabase Pro + R2 + Brevo (faixas públicas; não é fatura)", {"conservador": 60_000, "base": 50_000, "otimista": 45_000}),
    ("rule_activation_m", "Mês em que as regras são ATIVADAS (parecer + contrato)", "PREMISSA DE DECISÃO", "sem parecer hoje", {"conservador": 9, "base": 6, "otimista": 4}),
    ("activation_pct", "Organizações acima da franquia que aceitam contrato (%)", "PREMISSA DE MERCADO", "sem histórico", {"conservador": 50.0, "base": 70.0, "otimista": 85.0}),
]


def pct(v: float) -> float:
    return v / 100.0


def run(sc: str) -> dict:
    p = {k: v[4][sc] for k, v in ((x[0], x) for x in PREM)}
    f = {k: v[3] for k, v in FACTS.items()}
    rows = []
    cum = {"gross": 0, "settled": 0, "fee_calc": 0, "fee_due": 0, "fee_received": 0, "net_result": 0}
    orgs = p["orgs_m1"]
    settled_by_org_12m: list[int] = []   # histórico de liquidado (média por organização) para a franquia
    pending_settlement: list[int] = []   # liquidação atrasada
    for m in range(1, H + 1):
        orgs = p["orgs_m1"] * (1 + pct(p["orgs_growth"])) ** (m - 1)
        campaigns = orgs * p["campaigns_per_org"]
        n_don = campaigns * p["donors_per_campaign"]
        gross = int(n_don * p["ticket_cents"])
        refunds = int(gross * pct(p["refund_pct"]))
        net_gross = gross - refunds
        provider_fee = int(gross * pct(p["provider_pix_pct"]) + n_don * p["provider_fixed_cents"])
        pending_settlement.append(net_gross)
        settled = pending_settlement.pop(0) if len(pending_settlement) > p["settle_lag_m"] else 0
        per_org_settled = settled / orgs if orgs else 0
        settled_by_org_12m.append(per_org_settled)
        trailing = sum(settled_by_org_12m[-12:])
        # franquia: só a parcela do liquidado acima da franquia (por organização) gera obrigação devida; recurso público isento
        above = max(0.0, trailing - f["allowance_cents"]) if trailing else 0.0
        share_above = min(1.0, above / trailing) if trailing else 0.0
        private_share = 1 - pct(p["public_share_pct"])
        fee_calc = int(settled * private_share * f["donation_fee_bps"] / 10_000)
        active = m >= p["rule_activation_m"] + max(1, round(f["notice_days"] / 30))
        fee_due = int(fee_calc * share_above * pct(p["activation_pct"])) if active else 0
        inst_gross = int(p["inst_deals_m"] * p["inst_ticket_cents"])
        inst_fee_due = int(inst_gross * private_share * f["institutional_fee_bps"] / 10_000 * pct(p["activation_pct"])) if active else 0
        contract_gross = int(p["contracts_m"] * p["contract_gross_cents"])
        contract_fee_due = int(contract_gross * private_share * f["contract_fee_bps"] / 10_000 * pct(p["activation_pct"])) if active else 0
        ai_rev = int(orgs * p["ai_ops_per_org"] * f["ai_credit_price_cents"])
        due_total = fee_due + inst_fee_due + contract_fee_due
        received = int(due_total * (1 - pct(p["default_pct"]))) + ai_rev
        taxes = int(received * pct(p["tax_pct"]))
        costs = int(orgs * p["support_cents_org"]) + p["infra_cents_m"]
        net = received - taxes - costs
        cum["gross"] += gross; cum["settled"] += settled; cum["fee_calc"] += fee_calc; cum["fee_due"] += due_total
        cum["fee_received"] += received; cum["net_result"] += net
        rows.append({"m": m, "orgs": round(orgs, 1), "campaigns": round(campaigns, 1), "donations": round(n_don), "gross_cents": gross, "refund_cents": refunds,
                     "provider_fee_cents": provider_fee, "settled_cents": settled, "fee_calculated_cents": fee_calc, "fee_due_cents": fee_due,
                     "institutional_fee_due_cents": inst_fee_due, "contract_fee_due_cents": contract_fee_due, "ai_credits_cents": ai_rev,
                     "received_cents": received, "taxes_cents": taxes, "costs_cents": costs, "net_cents": net, "rules_active": active,
                     "share_above_allowance": round(share_above, 3)})
    be = next((r["m"] for r in rows if r["net_cents"] > 0), None)
    worst = min(0, min(sum(r["net_cents"] for r in rows[:i + 1]) for i in range(len(rows))))
    return {"scenario": sc, "rows": rows, "cumulative": cum, "break_even_month": be, "working_capital_need_cents": -worst}


def sensitivity(base: dict) -> list[dict]:
    """Varia uma premissa por vez (±25 %) no cenário base e mede o recebido acumulado em 24 meses."""
    out = []
    keys = ["orgs_growth", "ticket_cents", "donors_per_campaign", "provider_pix_pct", "default_pct", "public_share_pct", "activation_pct"]
    ref = run("base")["cumulative"]["fee_received"]
    for k in keys:
        for d in (-0.25, 0.25):
            saved = next(x for x in PREM if x[0] == k)[4]["base"]
            next(x for x in PREM if x[0] == k)[4]["base"] = saved * (1 + d)
            v = run("base")["cumulative"]["fee_received"]
            next(x for x in PREM if x[0] == k)[4]["base"] = saved
            out.append({"premissa": k, "variacao": f"{d:+.0%}", "recebido_24m_cents": v, "delta_pct": round((v - ref) / ref * 100, 1) if ref else None})
    return out


def brl(c: int) -> str:
    return f"R$ {c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    res = {sc: run(sc) for sc in SC}
    sens = sensitivity(res["base"])
    (OUT / "modelo_24m.json").write_text(json.dumps({"facts": FACTS, "premises": PREM, "results": res, "sensitivity": sens}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    # xlsx
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Premissas"
    ws.append(["chave", "rótulo", "natureza", "fonte", *SC])
    for k, (lab, nat, src, val) in FACTS.items():
        ws.append([k, lab, nat, src, val, val, val])
    for k, lab, nat, src, vals in PREM:
        ws.append([k, lab, nat, src, *[vals[s] for s in SC]])
    for sc in SC:
        w = wb.create_sheet(sc)
        cols = list(res[sc]["rows"][0].keys())
        w.append(cols)
        for r in res[sc]["rows"]:
            w.append([r[c] for c in cols])
        w.append([])
        w.append(["acumulado 24m"] + [res[sc]["cumulative"].get(c.replace("_cents", ""), "") for c in cols[1:]])
        w.append(["ponto de equilíbrio (mês)", res[sc]["break_even_month"] or "não atinge em 24 meses"])
        w.append(["necessidade de capital de giro (centavos)", res[sc]["working_capital_need_cents"]])
    w = wb.create_sheet("Sensibilidade (base)")
    w.append(["premissa", "variação", "recebido 24m (centavos)", "delta %"])
    for s in sens:
        w.append([s["premissa"], s["variacao"], s["recebido_24m_cents"], s["delta_pct"]])
    wb.save(OUT / "IMPACTO_MODELO_24M_v0340.xlsx")
    # gráfico
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for sc in SC:
        ax.plot([r["m"] for r in res[sc]["rows"]], [sum(x["net_cents"] for x in res[sc]["rows"][:i + 1]) / 100 for i in range(H)], label=f"{sc} — resultado acumulado")
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xlabel("mês"); ax.set_ylabel("R$"); ax.set_title("Resultado líquido acumulado em 24 meses — HIPÓTESES, regras inativas hoje")
    ax.legend(); fig.tight_layout(); fig.savefig(OUT / "g1_resultado_acumulado.png", dpi=120)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    b = res["base"]["rows"]
    ax.plot([r["m"] for r in b], [r["fee_calculated_cents"] / 100 for r in b], label="taxa CALCULADA (doações)")
    ax.plot([r["m"] for r in b], [r["fee_due_cents"] / 100 for r in b], label="taxa DEVIDA (após franquia, aviso e ativação)")
    ax.plot([r["m"] for r in b], [r["received_cents"] / 100 for r in b], label="RECEBIDO (todas as fontes, após inadimplência)")
    ax.set_xlabel("mês"); ax.set_ylabel("R$/mês"); ax.set_title("Cenário base: calculada ≠ devida ≠ recebida"); ax.legend(); fig.tight_layout()
    fig.savefig(OUT / "g2_calculada_devida_recebida.png", dpi=120)
    # md
    lines = ["# Modelo econômico de 24 meses — ecossistema financeiro (v0.34.0)", "",
             "> Gerado por `scripts/analysis/financial_model_24m_v0340.py`. Toda regra comercial está INATIVA; nenhuma doação real existe.",
             "> Os números abaixo são HIPÓTESES abertas (ver aba *Premissas* da planilha), não previsão nem dado de mercado.", "",
             "## Resumo por cenário (24 meses)", "", "| Cenário | Bruto doado | Liquidado | Taxa calculada (doações) | Taxas DEVIDAS (doação + aporte + acordo) | RECEBIDO (taxas após inadimplência + créditos de IA pré-pagos) | Resultado líquido | Ponto de equilíbrio | Capital de giro |",
             "|---|---|---|---|---|---|---|---|---|"]
    for sc in SC:
        c = res[sc]["cumulative"]
        lines.append(f"| {sc} | {brl(c['gross'])} | {brl(c['settled'])} | {brl(c['fee_calc'])} | {brl(c['fee_due'])} | {brl(c['fee_received'])} | {brl(c['net_result'])} | "
                     f"{'mês ' + str(res[sc]['break_even_month']) if res[sc]['break_even_month'] else 'não atinge'} | {brl(res[sc]['working_capital_need_cents'])} |")
    lines += ["", "## O que o modelo diz (e o que não diz)", "",
              "- A taxa sobre doações comunitárias, sozinha, **não sustenta a operação** em nenhum cenário: a franquia, a isenção de recurso público e o aviso prévio",
              "  reduzem a parcela devida, e a tarifa fixa do provedor pesa nos tíquetes baixos. Isso confirma a recomendação do pacote: não depender só das taxas sobre doações.",
              "- O que aproxima o equilíbrio são a taxa do acordo e os aportes institucionais (regras hoje INATIVAS) e os créditos de IA — e, fora do modelo, licenças institucionais",
              "  (contrárias à ADR-341; só com decisão do responsável).",
              "- Tudo depende do mês de ativação (parecer + contrato): antes dele, a plataforma calcula e mostra, mas não recebe.", "",
              "## Sensibilidade (cenário base, ±25 % em uma premissa por vez, recebido acumulado em 24 meses)", "", "| Premissa | Variação | Recebido 24m | Δ |", "|---|---|---|---|"]
    for s in sens:
        lines.append(f"| {s['premissa']} | {s['variacao']} | {brl(s['recebido_24m_cents'])} | {s['delta_pct']:+.1f} % |")
    lines += ["", "## Premissas", "", "| Chave | Rótulo | Natureza | Fonte | conservador | base | otimista |", "|---|---|---|---|---|---|---|"]
    for k, (lab, nat, src, val) in FACTS.items():
        lines.append(f"| `{k}` | {lab} | {nat} | {src} | {val} | {val} | {val} |")
    for k, lab, nat, src, vals in PREM:
        lines.append(f"| `{k}` | {lab} | {nat} | {src} | {vals['conservador']} | {vals['base']} | {vals['otimista']} |")
    lines += ["", "Gráficos: `g1_resultado_acumulado.png`, `g2_calculada_devida_recebida.png`. Planilha: `IMPACTO_MODELO_24M_v0340.xlsx` (fórmulas abertas por linha)."]
    (OUT / "MODELO_24M_v0340.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for sc in SC:
        c = res[sc]["cumulative"]
        print(f"{sc:12s} recebido 24m {brl(c['fee_received']):>16s} resultado {brl(c['net_result']):>16s} equilíbrio {res[sc]['break_even_month']}")


if __name__ == "__main__":
    main()
