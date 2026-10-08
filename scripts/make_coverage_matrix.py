#!/usr/bin/env python3
"""Gera docs/execution/COVERAGE_MATRIX.md a partir das EVIDÊNCIAS produzidas pelos testes (v0.25.0).

    python3 scripts/make_coverage_matrix.py           # escreve
    python3 scripts/make_coverage_matrix.py --check   # sai 1 se o arquivo não corresponde às evidências

Nenhum número aqui é digitado: vem de
  - docs/evidence/jornadas_v0250/relatorio.json   (test_v0250_jornadas — jornadas pela API)
  - docs/execution/ROUTE_RUNTIME_MATRIX.csv       (test_v0250_todas_as_telas — 218 telas no navegador)
  - docs/evidence/responsivo_v0250/resumo.json    (test_v0250_responsivo — telefone, 390 px)
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOR = ROOT / "docs" / "evidence" / "jornadas_v0250" / "relatorio.json"
TELAS = ROOT / "docs" / "execution" / "ROUTE_RUNTIME_MATRIX.csv"
RESP = ROOT / "docs" / "evidence" / "responsivo_v0250" / "resumo.json"
SAIDA = ROOT / "docs" / "execution" / "COVERAGE_MATRIX.md"

NOMES = {"osc": "OSC", "company": "Empresa (financiador)", "provider": "Profissional", "government": "Governo",
         "individual": "Apoiadora (pessoa física)", "admin": "Administração", "editor": "Editora (equipe)",
         "reviewer": "Revisor (equipe)", "support": "Suporte (equipe)", "anônimo": "Visitante sem login"}
SUCESSO = {"OK", "VAZIA", "RECUSA_CORRETA"}


def gerar() -> str:
    jor = json.loads(JOR.read_text(encoding="utf-8"))
    telas = list(csv.DictReader(TELAS.open(encoding="utf-8")))
    resp = json.loads(RESP.read_text(encoding="utf-8"))
    passos = jor["detalhe"]
    por_perfil = Counter(p["perfil"] for p in passos)
    falhas_perfil = Counter(p["perfil"] for p in passos if not p["ok"])
    jornadas_perfil: dict[str, set] = defaultdict(set)
    for p in passos:
        jornadas_perfil[p["perfil"]].add(p["jornada"])
    tel: dict[str, Counter] = defaultdict(Counter)
    for x in telas:
        tel[x["persona"]][x["estado"]] += 1
    fone = {k: v["telas_do_menu"] for k, v in resp["por_perfil"].items()}
    fone_falha = {k: len(v["com_rolagem_lateral"]) for k, v in resp["por_perfil"].items()}

    out = ["# Matriz de cobertura — v0.25.0", "",
           "> Gerada por `scripts/make_coverage_matrix.py` a partir das evidências dos testes. Não edite à mão.", "",
           "Três provas independentes, todas executadas (não planejadas):", "",
           f"- **Jornadas pela API** — {jor['passos']} passos em {len(jor['por_jornada'])} jornadas, "
           f"{jor['falhas']} falha(s). Fonte: `docs/evidence/jornadas_v0250/relatorio.json`.",
           f"- **Telas no navegador (Chromium)** — {len(telas)} visitas às {len({x['rota'] for x in telas})} rotas do roteador. "
           "Fonte: `docs/execution/ROUTE_RUNTIME_MATRIX.csv`.",
           f"- **Telefone (390 px)** — {resp['telas_visitadas']} telas de menu, {len(resp['falhas'])} falha(s). "
           "Fonte: `docs/evidence/responsivo_v0250/resumo.json`.", "",
           "## Por perfil", "",
           "| Perfil | Jornadas | Passos de API | Falhas de API | Telas visitadas | Com dado | Vazias | Recusa correta | Sem registro próprio | Outras | Telefone: telas | Telefone: vazam |",
           "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for k in ("osc", "company", "provider", "government", "individual", "admin", "editor", "reviewer", "support", "anônimo"):
        t = tel.get(k, Counter())
        outras = sum(n for e, n in t.items() if e not in SUCESSO and e != "SEM_REGISTRO")
        out.append(f"| {NOMES[k]} | {len(jornadas_perfil.get(k, ()))} | {por_perfil.get(k, 0)} | {falhas_perfil.get(k, 0)} | "
                   f"{sum(t.values())} | {t.get('OK', 0)} | {t.get('VAZIA', 0)} | {t.get('RECUSA_CORRETA', 0)} | "
                   f"{t.get('SEM_REGISTRO', 0)} | {outras} | {fone.get(k, '—')} | {fone_falha.get(k, '—')} |")
    out += ["", "**Como ler.** *Com dado*: a tela abriu com conteúdo vindo da API. *Vazias*: abriu e mostrou o estado",
            "vazio do produto (lista sem item, busca sem termo). *Recusa correta*: perfil que NÃO deve ver a tela",
            "recebeu \"área não disponível\" (ou foi mandado entrar). *Sem registro próprio*: a tela depende de um",
            "registro e esse perfil não participa de nenhum daquele tipo na demonstração — a tela é provada por",
            "outro perfil que participa. *Outras*: qualquer outro estado é falha e derruba o teste.", "",
            "## Jornadas", "", "| Jornada | Passos | Falhas |", "| --- | ---: | ---: |"]
    falha_j = Counter(p["jornada"] for p in passos if not p["ok"])
    for j, n in jor["por_jornada"].items():
        out.append(f"| {j} | {n} | {falha_j.get(j, 0)} |")
    out += ["", "## Por rota (resumo)", "",
            "Uma linha por rota; a coluna de perfis mostra o estado de cada visita (o detalhe completo, com",
            "URL, chamadas de API e tempo, está no CSV).", "",
            "| Rota | Visitas | Estados por perfil |", "| --- | ---: | --- |"]
    por_rota: dict[str, list] = defaultdict(list)
    for x in telas:
        por_rota[x["rota"]].append(x)
    abrev = {"OK": "ok", "VAZIA": "vazia", "RECUSA_CORRETA": "recusa", "SEM_REGISTRO": "s/registro"}
    for rota in sorted(por_rota):
        vs = por_rota[rota]
        out.append(f"| `{rota}` | {len(vs)} | " + ", ".join(f"{x['persona']}: {abrev.get(x['estado'], x['estado'])}" for x in vs) + " |")
    return "\n".join(out) + "\n"


def main() -> int:
    novo = gerar()
    if "--check" in sys.argv:
        atual = SAIDA.read_text(encoding="utf-8") if SAIDA.exists() else ""
        if atual != novo:
            print("COVERAGE_MATRIX.md não corresponde às evidências: rode python3 scripts/make_coverage_matrix.py")
            return 1
        print("matriz de cobertura conforme as evidências")
        return 0
    SAIDA.write_text(novo, encoding="utf-8")
    print(f"{SAIDA.relative_to(ROOT)}: {novo.count(chr(10))} linhas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
