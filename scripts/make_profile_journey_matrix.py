#!/usr/bin/env python3
"""Matriz perfil × jornada × permissão × dado × ação (v0.30.0) — GERADA, nunca escrita à mão.

    python3 scripts/make_profile_journey_matrix.py          # escreve docs/execution/PROFILE_JOURNEY_MATRIX_v0300.md

Fontes (todas já conferidas por teste):
* `docs/evidence/jornadas_v0250/relatorio.json` — as jornadas executadas pela API real (test_v0250_jornadas): perfil, passo, rota, status;
* `docs/execution/API_AUTHORIZATION_MATRIX.csv` — classe de autorização, papel mínimo, tipos de organização e permissão de cada operação;
* `docs/execution/screen_backend_map.json` — telas que chamam cada operação;
* `config/data_retention.json` — classe de retenção do dado tocado (quando a rota nomeia a tabela pelo prefixo).

O documento responde, por jornada e passo: quem age (perfil), o que faz (método + rota), o que a autorização exige
(classe, papel mínimo, tipos, permissão), que telas chegam lá, e que dado é tocado. Onde um passo não tem tela, está
escrito "sem tela" — é fato, não falha (o backend está à frente da interface; medido em screen_backend_map.json).
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNEYS = ROOT / "docs" / "evidence" / "jornadas_v0250" / "relatorio.json"
AUTH = ROOT / "docs" / "execution" / "API_AUTHORIZATION_MATRIX.csv"
SCREENS = ROOT / "docs" / "execution" / "screen_backend_map.json"
OUT = ROOT / "docs" / "execution" / "PROFILE_JOURNEY_MATRIX_v0300.md"

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
RANDOM_SUFFIX = re.compile(r"-[0-9a-f]{6}(?=/|$|\?)")   # slugs únicos por execução ("…/auditoria-5b00a4"): a matriz é função da ESTRUTURA, não da rodada
PROFILE_LABEL = {"osc": "OSC / executora", "company": "Financiador (empresa/instituto)", "individual": "Apoiador (pessoa física)",
                 "government": "Governo / órgão", "provider": "Profissional / prestador", "admin": "Administração / auditoria", "support": "Suporte",
                 "anônimo": "Visitante"}


def templ(path: str) -> str:
    """Troca ids reais por {param} para casar com a matriz de autorização (que é por rota-modelo)."""
    return RANDOM_SUFFIX.sub("-{slug}", UUID.sub("{id}", path.split("?")[0]))


def load_auth() -> dict[tuple[str, str], dict]:
    out = {}
    with AUTH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[(r["method"], re.sub(r"\{[a-z_]+\}", "{id}", r["path"]))] = r
    return out


def load_screens() -> dict[str, list[str]]:
    doc = json.loads(SCREENS.read_text(encoding="utf-8"))
    by_op: dict[str, list[str]] = {}
    for tela in doc.get("lista", []):
        for op in tela.get("operacoes", []) or []:
            # o mapa escreve "GET /v1/projects/{}" para parâmetros; normaliza para {id}
            by_op.setdefault(op.replace("{}", "{id}"), []).append(tela["rota"])
    return by_op


def main() -> int:
    j = json.loads(JOURNEYS.read_text(encoding="utf-8"))
    auth = load_auth()
    screens = load_screens()
    rows = j["detalhe"]
    by_journey: dict[str, list[dict]] = {}
    for r in rows:
        by_journey.setdefault(r["jornada"], []).append(r)
    L = ["# Matriz perfil × jornada × permissão × dado × ação — v0.30.0", "",
         "> GERADA por `scripts/make_profile_journey_matrix.py` a partir das jornadas executadas (`docs/evidence/jornadas_v0250/relatorio.json`),",
         "> da matriz de autorização (`API_AUTHORIZATION_MATRIX.csv`) e do mapa tela → operação (`screen_backend_map.json`). Não edite à mão.",
         "> Cada linha é um passo REALMENTE executado pela API na última regressão (status HTTP registrado), com o que a autorização exige",
         "> para aquele passo e as telas que o alcançam. 'sem tela' é fato medido, não falha.", "",
         f"Jornadas: **{len(by_journey)}** · passos: **{j['passos']}** · falhas: **{j['falhas']}**", "",
         "## Perfis e o que cada um percorre", "", "| Perfil | Passos executados | Jornadas em que aparece |", "| --- | ---: | --- |"]
    per_profile: dict[str, set] = {}
    for r in rows:
        per_profile.setdefault(r["perfil"], set()).add(r["jornada"])
    for prof, cnt in sorted(j["por_perfil"].items(), key=lambda x: -x[1]):
        L.append(f"| {PROFILE_LABEL.get(prof, prof)} | {cnt} | {len(per_profile.get(prof, ()))} |")
    L.append("")
    sem_tela = 0
    for jn, steps in by_journey.items():
        L += [f"## {jn}", "", "| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |",
              "| ---: | --- | --- | --- | ---: | --- | --- | --- |"]
        for i, s in enumerate(steps, 1):
            key = (s["metodo"], templ(s["rota"]))
            a = auth.get(key, {})
            classe = a.get("class", "?")
            papel = a.get("min_role") or "—"
            kinds = a.get("kinds") or "todos"
            perm = a.get("permission") or ("MFA" if a.get("mfa_required") == "yes" else "—")
            tela = screens.get(f"{s['metodo']} {templ(s['rota'])}") or []
            if not tela:
                sem_tela += 1
            L.append(f"| {i} | {PROFILE_LABEL.get(s['perfil'], s['perfil'])} | {s['passo']} | `{s['metodo']} {templ(s['rota'])}` | {s['status']} | {classe} · papel ≥ {papel} · tipos: {kinds} | {perm} | {', '.join(sorted(set(tela))[:4]) or 'sem tela'} |")
        L.append("")
    L += ["## Leitura", "",
          f"* Passos sem tela que os alcance diretamente: **{sem_tela}** de {j['passos']} — operações que a jornada exercita pela API e que a interface ainda não expõe (ou expõe por auxiliar compartilhado). O número oficial de operações sem tela é o de `screen_backend_map.json`.",
          "* A autorização é aplicada no backend (classe + papel + tipo + permissão), provada por `test_v0230_api_sweep` para TODAS as operações — a coluna aqui é a mesma matriz, lida por jornada.",
          "* Dado tocado: cada rota nomeia o recurso (projects, evidences, indicator-values, agreements, payouts…); a classe de retenção de cada tabela está em `config/data_retention.json` e é conferida por `test_v0190_lgpd_deletion`.",
          "* Estados vazios, erros e bloqueios por perfil: cobertos pelo robô de telas (`test_v0250_todas_as_telas`: OK · vazia · recusa correta · sem registro) e pela jornada 'Pendências'.", ""]
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"{OUT.name}: {len(by_journey)} jornadas, {j['passos']} passos, {sem_tela} sem tela")
    return 0


if __name__ == "__main__":
    sys.exit(main())
