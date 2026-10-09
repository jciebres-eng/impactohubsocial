#!/usr/bin/env python3
"""Gera `AI_COST_MODEL.md` a partir de `config/ai_economics.json` e de `docs/evidence/ai_pilot_v0280.json` (v0.28.0).

Documento DERIVADO (o teste `backend/tests/test_v0280_ai_cost_model.py` regenera e compara). Separa, em cada número,
o que é MEDIDO (piloto local, painel) do que é [PREMISSA] (hipóteses declaradas). Responde às doze perguntas do
pedido com aritmética sobre as premissas — não prevê, simula.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "ai_economics.json"
PILOT = ROOT / "docs" / "evidence" / "ai_pilot_v0280.json"
OUT = ROOT / "AI_COST_MODEL.md"


def brl(cents: float) -> str:
    v = round(cents) / 100
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def cts(cents: float) -> str:
    """Centavos com duas casas: nas contas unitárias, arredondar a reais esconderia margens negativas pequenas."""
    return f"{cents:.2f}".replace(".", ",") + " ¢"


def op_cost_cents(cfg: dict, op: dict, external: bool | None = None) -> dict:
    """Custo variável unitário [PREMISSA]: modelo (tokens × preço) + infra + retries.

    `external` força o cenário: True = provedor externo contratado; False = motor local (o estado MEDIDO desta
    instalação, sem provedor). Por padrão usa `cfg["external_provider_configured"]` para as operações que aceitam externo."""
    ext = op["external"] and (cfg.get("external_provider_configured", False) if external is None else external)
    px = cfg["external_price_per_mtok_cents_hypothesis"]
    modelo = (op["tokens_in"] * px["input"] + op["tokens_out"] * px["output"]) / 1_000_000 if ext else 0.0
    infra = cfg["infra_cents_per_operation_hypothesis"]["external" if ext else "local"]
    retries = modelo * cfg["retry_rate_hypothesis"]
    return {"model": modelo, "infra": infra, "retries": retries, "total": modelo + infra + retries, "external": ext}


def unit_economics(cfg: dict, external: bool | None = None) -> list[dict]:
    rows = []
    cp = cfg["credit_price_cents_hypothesis"]
    for code, op in cfg["operations"].items():
        c = op_cost_cents(cfg, op, external)
        preco = op["credits"] * cp
        taxa_pix = preco * cfg["pix_fee_pct_hypothesis"] / 100
        imposto = preco * cfg["tax_pct_hypothesis"] / 100
        margem = preco - c["total"] - taxa_pix - imposto
        rows.append({"code": code, "category": op["category"], "credits": op["credits"], "price_cents": preco, "cost": c,
                     "pix_fee": taxa_pix, "tax": imposto, "margin": margem, "margin_pct": (margem / preco * 100) if preco else None,
                     "free_cost": c["total"], "external": op["external"]})
    return rows


def simulate(cfg: dict, sc: dict) -> list[dict]:
    """Mês a mês: usuários ativos → usuários de IA → operações por categoria → gratuitas / patrocinadas / pagas →
    custo variável, receita reconhecida (créditos consumidos × preço), custo da gratuidade, margem."""
    ops_by_cat: dict[str, list[tuple[str, dict]]] = {}
    for code, op in cfg["operations"].items():
        ops_by_cat.setdefault(op["category"], []).append((code, op))
    cp = cfg["credit_price_cents_hypothesis"]
    rows = []
    for m in range(1, cfg["horizon_months"] + 1):
        users = sc["active_users_month1"] + sc["growth_per_month"] * (m - 1)
        ai_users = users * sc["ai_user_share"]
        total_ops = ai_users * sc["ops_per_ai_user_month"]
        custo = receita = gratuidade = patrocinio = 0.0
        n_free = n_paid = n_spons = 0.0
        for cat, share in sc["category_mix"].items():
            ops = ops_by_cat.get(cat, [])
            if not ops:
                continue
            per_op = total_ops * share / len(ops)
            for _code, op in ops:
                c = op_cost_cents(cfg, op)["total"]
                free = per_op * op["free_share"]
                rest = per_op - free
                paid = rest * sc["paid_share_of_non_free"]
                spons = rest * sc["sponsored_share_of_non_free"]
                # o restante não executa (sem fonte): não custa, não rende
                n_free += free
                n_paid += paid
                n_spons += spons
                custo += (free + paid + spons) * c
                gratuidade += free * c
                receita += (paid + spons) * op["credits"] * cp          # patrocínio também é crédito comprado por alguém
                patrocinio += spons * op["credits"] * cp
        taxa = receita * cfg["pix_fee_pct_hypothesis"] / 100
        imposto = receita * cfg["tax_pct_hypothesis"] / 100
        suporte = users * cfg["support_cents_per_active_user_month_hypothesis"]
        rows.append({"month": m, "users": users, "ai_users": ai_users, "ops": total_ops, "free_ops": n_free, "paid_ops": n_paid, "sponsored_ops": n_spons,
                     "cost": custo, "free_cost": gratuidade, "revenue": receita, "sponsored_revenue": patrocinio, "pix_fee": taxa, "tax": imposto,
                     "support": suporte, "margin": receita - custo - taxa - imposto - suporte})
    return rows


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    pilot = json.loads(PILOT.read_text(encoding="utf-8")) if PILOT.exists() else None
    cp = cfg["credit_price_cents_hypothesis"]
    L: list[str] = []
    L += [f"# MODELO DE CUSTO E SUSTENTABILIDADE DA IA — v0.28.0 ({cfg['version']})", "",
          ("**Gerado por:** `scripts/make_ai_cost_model.py` a partir de `config/ai_economics.json` e `docs/evidence/ai_pilot_v0280.json` · "
           "**Conferido por:** `backend/tests/test_v0280_ai_cost_model.py`"), "",
          "> **O que é MEDIDO e o que é [PREMISSA].** Medido nesta instalação: latência do motor local de similaridade e o tamanho das",
          "> entradas (piloto, §1); execuções, créditos e custo externo apurado aparecem no painel `/v1/admin/ai/finance` quando",
          "> existem. **Nenhum provedor externo está configurado e a tabela de preço do provedor está vazia**: todo custo de modelo",
          "> abaixo é [PREMISSA] declarada em `config/ai_economics.json`. Preços de operação e de pacote são HIPÓTESES de teste do",
          "> proprietário (ADR-349), não preços de produção. **Receita real de IA desta instalação: R$ 0,00** (modo piloto).", "",
          "---", "", "## 1. Piloto — o que foi medido de verdade", ""]
    if pilot:
        L += [f"Medido em {pilot['measured_on']}, motor `{pilot['engine_version']}`, perfis sintéticos, nesta máquina:", "",
              "| Medição | p50 | p95 / máx | n |", "| --- | ---: | ---: | ---: |",
              f"| comparação de um par | {pilot['pair_compare_ms']['p50']} ms | {pilot['pair_compare_ms']['p95']} ms | {pilot['pair_compare_ms']['n']} |",
              f"| originalidade contra 50 candidatos | {pilot['originality_50_ms']['p50']} ms | {pilot['originality_50_ms']['max']} ms | {pilot['originality_50_ms']['n']} |",
              f"| originalidade contra 200 candidatos | {pilot['originality_200_ms']['p50']} ms | {pilot['originality_200_ms']['max']} ms | {pilot['originality_200_ms']['n']} |",
              f"| entrada de um projeto | {pilot['input_chars_subject']} caracteres ≈ {pilot['approx_tokens_subject']} tokens (4 car./token, aproximação) | | |", "",
              "**Não medido:** " + "; ".join(pilot["what_is_not_measured"]) + ".", ""]
    else:
        L += ["Sem medição de piloto (rode `scripts/measure_ai_pilot.py`).", ""]
    L += ["## 2. Custo unitário e margem de contribuição por operação [PREMISSA]", "",
          (f"Preço do crédito: {brl(cp)} [PREMISSA] · modelo externo: {brl(cfg['external_price_per_mtok_cents_hypothesis']['input'])}/Mtok entrada, "
           f"{brl(cfg['external_price_per_mtok_cents_hypothesis']['output'])}/Mtok saída [PREMISSA] · infra {brl(cfg['infra_cents_per_operation_hypothesis']['local'])} local / "
           f"{brl(cfg['infra_cents_per_operation_hypothesis']['external'])} externa por operação [PREMISSA] · retries {cfg['retry_rate_hypothesis']:.0%} · "
           f"tarifa PIX {cfg['pix_fee_pct_hypothesis']}% · impostos {cfg['tax_pct_hypothesis']}% [PREMISSA]"), "",
          "| Operação | Cat. | Créditos | Preço | Custo modelo | Infra+retries | Tarifa | Imposto | Margem de contribuição | % |",
          "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    ue = unit_economics(cfg, external=True)      # [PREMISSA] com provedor externo contratado para as operações que o aceitam
    ue_local = unit_economics(cfg, external=False)   # estado MEDIDO desta instalação: tudo no motor local
    for r in ue:
        L.append(f"| `{r['code']}` | {r['category']} | {r['credits']} | {brl(r['price_cents'])} | {cts(r['cost']['model'])} | {cts(r['cost']['infra'] + r['cost']['retries'])} | "
                 f"{cts(r['pix_fee'])} | {cts(r['tax'])} | **{cts(r['margin'])}** | {r['margin_pct']:.0f}% |")
    deficit = [r for r in ue if r["margin"] < 0]
    L += ["", "Margem de contribuição = receita reconhecida − custos variáveis − tarifa − imposto. Não é lucro: despesas fixas e suporte ficam fora (§4).",
          "A tabela acima supõe PROVEDOR EXTERNO contratado para as operações de assistência (A/B). Hoje NÃO há provedor: essas operações "
          f"rodam no motor local e custam só infraestrutura ({brl(cfg['infra_cents_per_operation_hypothesis']['local'])} [PREMISSA]).",
          ("**Operações DEFICITÁRIAS com provedor externo nas premissas: " + ", ".join(f"`{r['code']}` ({cts(r['margin'])})" for r in deficit) +
           ".** A regra do pedido é explícita: não manter cobrança deficitária por inércia — antes de ligar um provedor externo, a operação precisa de "
           "preço maior, limite de tokens menor, cache por versão ou permanência no motor local. Este documento registra o achado; a decisão é da administração "
           "(versão nova no catálogo, sem código).") if deficit else "Nenhuma operação é deficitária sob estas premissas.", "",
          "## 3. Quanto custa a gratuidade (cota) [PREMISSA sobre custo; cotas MEDIDAS no catálogo]", "",
          f"Cota de boas-vindas: {cfg['welcome_quota_credits']} créditos por organização (uma vez; uma por pessoa). Cota leve mensal: {cfg['monthly_light_quota_credits']} créditos (OSC e profissional).", "",
          "| Operação | Custo variável de UMA execução gratuita | Execuções gratuitas que a cota de boas-vindas cobre |", "| --- | ---: | ---: |"]
    for r in ue:
        L.append(f"| `{r['code']}` | {cts(r['free_cost'])} (com provedor) / {cts(next(x['free_cost'] for x in ue_local if x['code'] == r['code']))} (local) | {cfg['welcome_quota_credits'] // r['credits'] if r['credits'] else '—'} |")
    L += ["", (f"Teto de subsídio declarado para o piloto: **{brl(cfg['subsidy_cap_cents_month'])}/mês** [PREMISSA]. A cada mês o painel compara o custo "
               "medido das execuções gratuitas (`free_quota_uses` × custo) com este teto; acima dele, a política `welcome.v1` é reduzida pela administração "
               "(sem código) ou a gratuidade passa a patrocínio institucional (§5)."), "",
          "## 4. Três cenários, 12 meses [PREMISSA]", ""]
    resumo = []
    for key, sc in cfg["scenarios"].items():
        rows = simulate(cfg, sc)
        tot = {k: sum(r[k] for r in rows) for k in ("ops", "free_ops", "paid_ops", "sponsored_ops", "cost", "free_cost", "revenue", "sponsored_revenue", "pix_fee", "tax", "support", "margin")}
        resumo.append((sc["label"], rows[-1]["users"], tot))
        L += [(f"### 4.{list(cfg['scenarios']).index(key) + 1} {sc['label']} — {sc['active_users_month1']} usuários no mês 1, +{sc['growth_per_month']}/mês, "
               f"{sc['ai_user_share']:.0%} usam IA, {sc['ops_per_ai_user_month']} operações/usuário de IA/mês"), "",
              "| Mês | Usuários | Usuários de IA | Operações | Gratuitas | Patrocinadas | Pagas | Custo variável | Custo da gratuidade | Receita reconhecida | Margem (após tarifa, imposto e suporte) |",
              "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for r in rows:
            L.append(f"| {r['month']} | {r['users']:.0f} | {r['ai_users']:.0f} | {r['ops']:.0f} | {r['free_ops']:.0f} | {r['sponsored_ops']:.0f} | {r['paid_ops']:.0f} | "
                     f"{brl(r['cost'])} | {brl(r['free_cost'])} | {brl(r['revenue'])} | {brl(r['margin'])} |")
        L += [f"| **12 meses** | {rows[-1]['users']:.0f} | | {tot['ops']:.0f} | {tot['free_ops']:.0f} | {tot['sponsored_ops']:.0f} | {tot['paid_ops']:.0f} | {brl(tot['cost'])} | {brl(tot['free_cost'])} | {brl(tot['revenue'])} | **{brl(tot['margin'])}** |", ""]
    L += ["### 4.4 Resumo", "", "| Cenário | Usuários no mês 12 | Operações | Custo variável | Custo da gratuidade | Receita reconhecida (dos quais patrocínio) | Margem |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label, users, tot in resumo:
        L.append(f"| {label} | {users:.0f} | {tot['ops']:.0f} | {brl(tot['cost'])} | {brl(tot['free_cost'])} | {brl(tot['revenue'])} ({brl(tot['sponsored_revenue'])}) | **{brl(tot['margin'])}** |")
    L += ["", "## 5. Sensibilidade: e se o uso dobrar? [PREMISSA]", ""]
    for key, sc in cfg["scenarios"].items():
        sc2 = dict(sc, ops_per_ai_user_month=sc["ops_per_ai_user_month"] * 2)
        a = simulate(cfg, sc)
        b = simulate(cfg, sc2)
        L.append(f"* **{sc['label']}**: dobrando operações por usuário, custo variável {brl(sum(r['cost'] for r in a))} → {brl(sum(r['cost'] for r in b))}; "
                 f"custo da gratuidade {brl(sum(r['free_cost'] for r in a))} → {brl(sum(r['free_cost'] for r in b))}; margem {brl(sum(r['margin'] for r in a))} → {brl(sum(r['margin'] for r in b))}. "
                 "A gratuidade escala linearmente com o uso: é ela que precisa de teto (§3), não a operação paga.")
    L += ["", "## 6. Sensibilidade ao preço do provedor externo [PREMISSA]", "",
          "| Preço do modelo | Custo de `assist.draft_document` | Margem da operação (10 créditos) |", "| --- | ---: | ---: |"]
    for mult, nome in ((0.5, "metade"), (1.0, "premissa"), (2.0, "dobro"), (4.0, "quádruplo")):
        c2 = json.loads(json.dumps(cfg))
        c2["external_price_per_mtok_cents_hypothesis"]["input"] *= mult
        c2["external_price_per_mtok_cents_hypothesis"]["output"] *= mult
        r = next(x for x in unit_economics(c2, external=True) if x["code"] == "assist.draft_document")
        L.append(f"| {nome} | {cts(r['cost']['total'])} | {cts(r['margin'])} ({r['margin_pct']:.0f}%) |")
    L += ["", "## 7. As doze perguntas, respondidas pelas premissas", ""]
    base = simulate(cfg, cfg["scenarios"]["base"])
    tot_b = {k: sum(r[k] for r in base) for k in ("ops", "free_ops", "cost", "free_cost", "revenue", "margin")}
    custo_por_usuario = (tot_b["cost"] + sum(r["support"] for r in base)) / sum(r["users"] for r in base)
    cheapest = min(ue, key=lambda r: r["margin_pct"])
    cabem = f"{int(cfg['subsidy_cap_cents_month'] / max(tot_b['free_cost'] / max(tot_b['free_ops'], 1), 0.01)):,}".replace(",", ".")
    c4 = json.loads(json.dumps(cfg))
    c4["external_price_per_mtok_cents_hypothesis"]["input"] *= 4
    c4["external_price_per_mtok_cents_hypothesis"]["output"] *= 4
    pior_draft = next(r["margin"] for r in unit_economics(c4, external=True) if r["code"] == "assist.draft_document")
    L += [f"1. **Quanto custa manter cada perfil ativo?** No cenário base, {brl(custo_por_usuario)} por usuário-mês em custo variável de IA + suporte [PREMISSA]; o perfil não muda o custo — a categoria da operação muda.",
          f"2. **Quanto custa cada modalidade?** §2: de {cts(min(r['cost']['total'] for r in ue))} (motor local) a {cts(max(r['cost']['total'] for r in ue))} (rascunho com provedor externo) por execução [PREMISSA].",
          f"3. **Quantas operações gratuitas cabem no orçamento?** Com teto de {brl(cfg['subsidy_cap_cents_month'])}/mês e custo médio da execução gratuita de {cts(tot_b['free_cost'] / max(tot_b['free_ops'], 1))}, cabem ~{cabem} execuções gratuitas por mês.",
          f"4. **Custo mensal da gratuidade?** Cenário base: {brl(tot_b['free_cost'] / cfg['horizon_months'])}/mês em média; mês 12: {brl(base[-1]['free_cost'])}.",
          f"5. **Ponto de equilíbrio por categoria?** Com provedor externo, a menor margem é `{cheapest['code']}` ({cheapest['margin_pct']:.0f}%){' — deficitária' if cheapest['margin'] < 0 else ''}; no motor local (estado medido) todas cobrem o custo variável. O equilíbrio do TODO (gratuidade + suporte) chega no cenário base no mês {next((r['month'] for r in base if r['margin'] > 0), '—')}.",
          "6. **Margem por operação?** §2, coluna 'Margem de contribuição'.",
          f"7. **Pior cenário plausível?** Agressivo com uso dobrado (§5) e provedor ao quádruplo (§6): `assist.draft_document` fica com margem de {cts(pior_draft)} ({'ainda positiva' if pior_draft > 0 else 'NEGATIVA: a operação não pode ser vendida a este preço com esse provedor'}); a gratuidade quadruplica — é o caso que exige teto, patrocínio e reprecificação por versão nova.",
          f"8. **Limite de exposição financeira aceitável?** O declarado: {brl(cfg['subsidy_cap_cents_month'])}/mês de subsídio [PREMISSA]. O painel acusa quando o custo medido da gratuidade passa disso.",
          "9. **Se o consumo dobrar?** §5: custo e gratuidade dobram; a margem das operações pagas também — o sinal de risco é a razão gratuitas/pagas, não o volume.",
          "10. **Quais funcionalidades precisam de limites mais rigorosos?** `similarity.set` (até 20 projetos) e qualquer lote (`similarity.batch`, planejada e NÃO implementada); operações externas de categoria B (tamanho de entrada e `max_output_tokens` da faixa).",
          ("11. **Quando o patrocínio é melhor que a gratuidade subsidiada?** Sempre que a execução custa mais do que a cota cobre para a organização beneficiada: o patrocínio é crédito comprado por quem tem capacidade de pagar (receita), a gratuidade é custo. No cenário base, "
           f"{brl(sum(r['sponsored_revenue'] for r in base))} dos {brl(tot_b['revenue'])} de receita vêm de patrocínio."),
          "12. **Quais operações devem usar modelo mais barato, cache ou assíncrono?** Cache já vale para similaridade (mesmos dados = sem nova cobrança) e deve valer para resumo por versão de projeto; categoria A deve ficar no motor local sempre que a qualidade bastar; lote só assíncrono com orçamento por tarefa (não implementado).",
          "", "## 8. O que este modelo NÃO contém", "",
          "* Preço do provedor real, câmbio e tabela vigente: a `ai_price_table` nasce vazia e o painel marca `no_price_table` até a administração cadastrar.",
          "* Reconhecimento contábil de créditos não consumidos (passivo) e regra de devolução/expiração: carta legal amarela de `ai.credits_prepaid`.",
          "* Despesas fixas e margem líquida: fora do escopo (UNIT_ECONOMICS.md).",
          "* Qualquer número de uso real: esta instalação não tem clientes; tudo aqui é [PREMISSA] até o painel medir.", ""]
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"{OUT.name}: {len(L)} linhas; " + "; ".join(f"{label} margem 12m {brl(tot['margin'])}" for label, _, tot in resumo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
