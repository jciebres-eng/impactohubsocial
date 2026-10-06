#!/usr/bin/env python3
"""Gera `PRICING_CATALOG.md` a partir de `config/plans.json`.

POR QUE GERADO, E NÃO ESCRITO

Um catálogo de preços escrito à mão fica desatualizado na primeira mudança de tabela — e um
documento de preço desatualizado é pior do que nenhum, porque alguém o cita numa proposta. Aqui o
documento é derivado da mesma fonte que a migração carrega, então ele não tem como divergir dela
sem que alguém rode este script e veja a diferença no diff.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config" / "plans.json").read_text(encoding="utf-8"))

TIER_ORDEM = {"free": 0, "plus": 1, "premium": 2, "gov": 3}


def brl(cents: int | None) -> str:
    if cents is None:
        return "—"
    if cents == 0:
        return "R$ 0,00"
    return "R$ " + f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> int:
    itens = [i for i in CFG["price_versions"]["items"] if not i.get("retire")]
    aposentados = [i for i in CFG["price_versions"]["items"] if i.get("retire")]
    preco = {(i["plan_key"], i["interval"]): i for i in itens}

    linhas = [
        "# CATÁLOGO DE PREÇOS — GERADO",
        "",
        f"**Pricing Version:** `{CFG.get('pricing_version')}` · **Catálogo:** `{CFG['version']}` · "
        f"**Moeda:** {CFG.get('currency', 'BRL')}",
        "",
        "> Gerado por `scripts/make_pricing_catalog.py` a partir de `config/plans.json` — não edite à",
        "> mão. A decisão comercial está em `PRICING_BIBLE.md`; a reconciliação com o que o código já",
        "> fazia está em `PRICING_RECONCILIATION.md`.",
        "",
        "---",
        "",
        "## 1. PLANOS",
        "",
        "| `plan_key` | Nome | Perfil | Faixa | Mensal | Anual | Piso de proposta | Contratação |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for key, p in sorted(CFG["plans"].items(),
                         key=lambda kv: (kv[1].get("role", ""),
                                         TIER_ORDEM.get(kv[1].get("tier"), 9), kv[0])):
        mes = preco.get((key, "month"))
        ano = preco.get((key, "year"))
        piso = p.get("quote_floor_cents")
        if p.get("tier") == "free":
            contratacao = "online (gratuito)"
        elif mes or ano:
            contratacao = "online"
        else:
            contratacao = "**proposta comercial**"
        linhas.append(
            f"| `{key}` | {p['name']} | {p.get('role')} | {p.get('tier')} | "
            f"{brl(mes['amount_cents'] if mes else (0 if p.get('tier') == 'free' else None))} | "
            f"{brl(ano['amount_cents'] if ano else None)} | {brl(piso)} | {contratacao} |")

    linhas += ["", "---", "", "## 2. VERSÕES DE PREÇO VIGENTES", "",
               "| Plano | Intervalo | Valor | Tributos | Decisão |",
               "| --- | --- | ---: | --- | --- |"]
    for i in sorted(itens, key=lambda x: (x["plan_key"], x["interval"])):
        linhas.append(f"| `{i['plan_key']}` | {i['interval']} | {brl(i['amount_cents'])} | "
                      f"{i.get('tax_behavior', 'unspecified')} | {i['reason']} |")

    linhas += ["", "---", "", "## 3. VERSÕES APOSENTADAS", "",
               "Aposentar **não é apagar**: o preço de ontem explica o contrato de ontem. Um item com",
               "`retire: true` fecha a vigência e não abre nenhuma nova.", "",
               "| Faixa | Intervalo | Moeda | Motivo |", "| --- | --- | --- | --- |"]
    for i in aposentados:
        linhas.append(f"| {i.get('applies_to_tier', '—')} | {i['interval']} | {i['currency']} | "
                      f"{i['reason']} |")

    linhas += ["", "---", "", "## 4. LIMITES POR PLANO", "",
               "`null` significa **ilimitado**. Entre fontes (plano base, assinatura, licença,",
               "convênio, teste), vale sempre a mais favorável.", ""]
    chaves: list[str] = []
    for p in CFG["plans"].values():
        for k in (p.get("limits") or {}):
            if k not in chaves:
                chaves.append(k)
    linhas.append("| Plano | " + " | ".join(f"`{k}`" for k in chaves) + " |")
    linhas.append("| --- | " + " | ".join("---:" for _ in chaves) + " |")
    for key, p in sorted(CFG["plans"].items()):
        lim = p.get("limits") or {}
        celulas = ["ilimitado" if (k in lim and lim[k] is None) else str(lim.get(k, "—"))
                   for k in chaves]
        linhas.append(f"| `{key}` | " + " | ".join(celulas) + " |")

    linhas += ["", "---", "", "## 5. NUNCA VENDÁVEL", "",
               "Nenhum plano libera estas capacidades, em nenhuma faixa, por nenhum valor:", ""]
    for f in CFG.get("never_sellable", []):
        linhas.append(f"* `{f}`")
    linhas += ["",
               "Travado por teste: `test_no_plan_sells_anything_from_the_list` e",
               "`test_no_code_path_turns_a_plan_into_a_score`.", ""]

    (ROOT / "PRICING_CATALOG.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"PRICING_CATALOG.md: {len(CFG['plans'])} planos, {len(itens)} versões vigentes, "
          f"{len(aposentados)} aposentadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
