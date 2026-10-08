#!/usr/bin/env python3
"""Gera `24_MONTH_FINANCIAL_MODEL.md` a partir de `config/economic_model.json` (v0.27.0, ADR-341).

O documento é DERIVADO: toda linha numérica sai daqui, e `backend/tests/test_v0270_financial_model.py`
regenera e compara com o que está no repositório — um número editado à mão no documento reprova.

O que o modelo faz: aplica os percentuais da camada econômica (3,5% plataforma, 1,5% participação de
autoria) a volumes de operação que são PREMISSA DECLARADA (3 novos clientes financiadores por mês,
ticket médio e ritmo de quitação por cenário). O que ele não faz: prever. Não há custo, não há margem,
não há "resultado": a camada registrada só vira receita quando a operação é quitada e a regra comercial
está ativa — hoje ela NÃO está (carta amarela), então a receita real desta instalação é zero por
construção, e o documento diz isso na primeira linha.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "economic_model.json"
OUT = ROOT / "24_MONTH_FINANCIAL_MODEL.md"


def brl(cents: float) -> str:
    v = round(cents) / 100
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def pct(bps: int) -> str:
    return f"{bps / 100:.2f}".replace(".", ",") + "%"


def simulate(cfg: dict, sc: dict) -> list[dict]:
    """Mês a mês: clientes acumulados → operações ativadas → camada registrada → quitação → camada paga."""
    h = cfg["horizon_months"]
    bps_p, bps_a = cfg["platform_service_bps"], cfg["proponent_participation_bps"]
    novos = cfg["new_funding_clients_per_month"]
    ops_ano = sc["operations_per_client_per_year"]
    ticket = sc["avg_operation_cents"]
    quit = sc["settled_share"]
    lag = sc["months_to_settle"]
    ramp = sc["ramp_months"]
    rows: list[dict] = []
    clientes = 0
    registrado_por_mes: list[int] = []
    for m in range(1, h + 1):
        clientes += novos
        # Rampa: nos primeiros `ramp` meses o cliente ainda está entrando (diagnóstico, acordo); a fração
        # de clientes "operando" cresce linearmente até 1.
        fator_rampa = min(1.0, m / ramp)
        ops = clientes * ops_ano / 12 * fator_rampa
        gmv = ops * ticket
        registrado = round(gmv * bps_p / 10_000)
        participacao = round(gmv * bps_a / 10_000)
        registrado_por_mes.append(registrado)
        # Quitação: a fração `quit` das operações ativadas há `lag` meses é quitada neste mês.
        pago = round(registrado_por_mes[m - 1 - lag] * quit) if m - 1 - lag >= 0 else 0
        rows.append({"month": m, "clients": clientes, "operations": round(ops, 2), "gmv_cents": round(gmv),
                     "platform_registered_cents": registrado, "participation_cents": participacao,
                     "platform_paid_cents": pago})
    return rows


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    bps_p, bps_a = cfg["platform_service_bps"], cfg["proponent_participation_bps"]
    L: list[str] = []
    L.append("# MODELO FINANCEIRO DE 24 MESES — v0.27.0 (sem assinatura, ADR-341)")
    L.append("")
    L.append(f"**Pricing Version:** {cfg['pricing_version']} · **Camada econômica:** {pct(bps_p)} plataforma + {pct(bps_a)} participação de autoria = {pct(bps_p + bps_a)} da operação financiada")
    L.append("**Gerado por:** `scripts/make_24_month_model.py` a partir de `config/economic_model.json` · **Conferido por:** `backend/tests/test_v0270_financial_model.py`")
    L.append("")
    L.append("> **RECEITA REAL DESTA INSTALAÇÃO: R$ 0,00.** A regra comercial `contract.platform_service_fee` está INATIVA (carta")
    L.append("> legal amarela). A camada econômica é registrada e instruída, mas nada fica devido nem é cobrado até a carta verde.")
    L.append("> Tudo abaixo é SIMULAÇÃO sobre HIPÓTESES DECLARADAS — não é projeção, não é meta, não é dado apurado.")
    L.append(">")
    L.append("> **Não existe assinatura.** O modelo da v0.21.0 (MRR de mensalidades a partir do mês 16) foi retirado com a")
    L.append("> assinatura. A receita possível da plataforma nasce da operação financiada e de contratos avulsos (não modelados aqui).")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 1. A FÓRMULA (decorre do contrato e do catálogo, não é premissa)")
    L.append("")
    L.append("```")
    L.append(f"camada_registrada(op) = valor_financiado(op) × {bps_p} bps      -- congelada na matriz do acordo na ativação")
    L.append(f"participacao(op)      = valor_financiado(op) × {bps_a} bps      -- só com proponente elegível; NÃO é receita da plataforma")
    L.append("camada_paga(mês)      = Σ camada_registrada das operações QUITADAS no mês   -- só isto é receita, e só com a regra ativa")
    L.append("GMV ≠ receita: o valor financiado vai do financiador ao projeto; a plataforma não custodia (ADR-284).")
    L.append("```")
    L.append("")
    L.append("## 2. SENSIBILIDADE — uma operação, do menor ao maior ticket")
    L.append("")
    L.append("| Valor financiado | Projeto recebe (modo descontado) | Plataforma (" + pct(bps_p) + ") | Participação de autoria (" + pct(bps_a) + ") | Camada total |")
    L.append("| ---: | ---: | ---: | ---: | ---: |")
    for v in cfg["sensitivity_operations_cents"]:
        p = v * bps_p // 10_000
        a = v * bps_a // 10_000
        L.append(f"| {brl(v)} | {brl(v - p - a)} | {brl(p)} | {brl(a)} | {brl(p + a)} |")
    L.append("")
    L.append("Com `fee_mode = additional` o projeto recebe o valor cheio e o financiador paga a camada à parte; a soma fecha nos dois modos (CHECK no banco).")
    L.append("")
    L.append("## 3. GMV NECESSÁRIO PARA CADA PATAMAR DE RECEITA (só aritmética)")
    L.append("")
    L.append("| Receita da plataforma (camada PAGA) | GMV quitado necessário | Operações de " + brl(cfg["scenarios"]["base"]["avg_operation_cents"]) + " |")
    L.append("| ---: | ---: | ---: |")
    base_ticket = cfg["scenarios"]["base"]["avg_operation_cents"]
    for t in cfg["revenue_targets_cents"]:
        gmv = t * 10_000 / bps_p
        ops = f"{gmv / base_ticket:,.0f}".replace(",", ".")
        L.append(f"| {brl(t)} | {brl(gmv)} | {ops} |")
    L.append("")
    L.append("## 4. TRÊS CENÁRIOS — PREMISSAS, NÃO PREVISÕES")
    L.append("")
    L.append(f"Premissa comum: **{cfg['new_funding_clients_per_month']} novos clientes financiadores por mês**. O que muda entre cenários:")
    L.append("")
    L.append("| Cenário | Ticket médio por operação | Operações por cliente/ano | Fração quitada | Meses até quitar | Rampa (meses) |")
    L.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for sc in cfg["scenarios"].values():
        L.append(f"| {sc['label']} | {brl(sc['avg_operation_cents'])} | {sc['operations_per_client_per_year']} | {int(sc['settled_share'] * 100)}% | {sc['months_to_settle']} | {sc['ramp_months']} |")
    L.append("")
    resumo = []
    for key, sc in cfg["scenarios"].items():
        rows = simulate(cfg, sc)
        tot_gmv = sum(r["gmv_cents"] for r in rows)
        tot_reg = sum(r["platform_registered_cents"] for r in rows)
        tot_pago = sum(r["platform_paid_cents"] for r in rows)
        tot_part = sum(r["participation_cents"] for r in rows)
        resumo.append((sc["label"], tot_gmv, tot_reg, tot_pago, tot_part, rows[-1]["clients"]))
        L.append(f"### 4.{list(cfg['scenarios']).index(key) + 1} {sc['label']}")
        L.append("")
        L.append("| Mês | Clientes | Operações ativadas | GMV ativado | Camada registrada | Participação (não é receita) | Camada PAGA |")
        L.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for r in rows:
            L.append(f"| {r['month']} | {r['clients']} | {r['operations']:.2f} | {brl(r['gmv_cents'])} | {brl(r['platform_registered_cents'])} | {brl(r['participation_cents'])} | {brl(r['platform_paid_cents'])} |")
        L.append(f"| **24 meses** | {rows[-1]['clients']} | {sum(r['operations'] for r in rows):.2f} | {brl(tot_gmv)} | {brl(tot_reg)} | {brl(tot_part)} | **{brl(tot_pago)}** |")
        L.append("")
    L.append("## 5. RESUMO DOS CENÁRIOS (24 meses)")
    L.append("")
    L.append("| Cenário | Clientes no mês 24 | GMV ativado | Camada registrada | Camada PAGA (receita possível) | Participação de autoria |")
    L.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for label, g, r, p, a, c in resumo:
        L.append(f"| {label} | {c} | {brl(g)} | {brl(r)} | **{brl(p)}** | {brl(a)} |")
    L.append("")
    L.append("## 6. O QUE ESTE MODELO NÃO CONTÉM, E POR QUÊ")
    L.append("")
    L.append("* **Custo e margem.** O lado do custo continua vazio (`UNIT_ECONOMICS.md`); um modelo com receita simulada e custo inventado produz margem inventada.")
    L.append("* **Contratos avulsos/parcelados** (implantação, módulo institucional, inteligência territorial): valor negociado por quem tem alçada, sem base para premissa.")
    L.append("* **Receita de IA/API e marketplace:** zero por construção (sem preço de excedente publicado; comissão recusada).")
    L.append("* **Data de ativação da regra comercial:** depende de parecer jurídico/contábil externo (`BLOCKED_EXTERNAL_DEPENDENCY`). Até lá, a camada PAGA simulada é hipótese sobre hipótese.")
    L.append("* **Churn, LTV, CAC:** não existem sem assinatura e sem histórico; o painel os marca como não medidos com motivo.")
    L.append("")
    L.append("[PREMISSA] marca, neste repositório, qualquer número que venha de `config/economic_model.json` e não de registro. Todos os números deste documento são [PREMISSA], exceto os percentuais do catálogo e a aritmética sobre eles.")
    L.append("")
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"{OUT.name}: {len(L)} linhas; cenários: " + ", ".join(f"{nome} paga {brl(p)}" for nome, _, _, p, _, _ in resumo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
