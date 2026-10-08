#!/usr/bin/env python3
"""Gera MOTOR_COVERAGE_MATRIX.md — a matriz de cobertura dos motores exigida pelo PROMPT MASTER (v0.27.0).

Derivada de `impacto.engines.coverage` (mesma fonte de ENGINE_COVERAGE.md) mais a prova por jornada:
um motor conta como "coberto por jornada" quando alguma de suas rotas é chamada por `tests/demo_journeys.py`
ou por um teste E2E de interface (`tests/test_e2e_*.py`). O status final é VERDE / AMARELO / VERMELHO:

  VERDE    implementado, integrado, testado, com E2E (ou n/a por não ter rota própria) e com rastro;
  AMARELO  tudo acima menos rastro durável (observabilidade) ou E2E;
  VERMELHO qualquer coluna estrutural (implemented/integrated/tested) em "não".
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from impacto.engines import coverage  # noqa: E402

DEST = ROOT / "MOTOR_COVERAGE_MATRIX.md"
TESTS = ROOT / "backend" / "tests"


def _journey_sources() -> str:
    partes = []
    for f in sorted(TESTS.glob("demo_journeys.py")) + sorted(TESTS.glob("test_e2e_*.py")) + sorted(TESTS.glob("test_v0250_jornadas.py")):
        partes.append(f.read_text(encoding="utf-8"))
    return "\n".join(partes)


def _route_regex(route: str) -> re.Pattern:
    # /v1/projects/{project_id}/ready → /v1/projects/[^/\s"']+/ready
    pat = re.sub(r"\{[a-z_]+\}", r"[^/\\s\"']+", re.escape(route).replace(r"\{", "{").replace(r"\}", "}"))
    return re.compile(pat)


def main() -> int:
    t = coverage.table()
    fontes = _journey_sources()
    linhas = []
    cores = {"VERDE": 0, "AMARELO": 0, "VERMELHO": 0}
    for e in t["engines"]:
        jornada = any(_route_regex(r).search(fontes) for r in e["routes"]) if e["routes"] else None
        estrutural = e["implemented"] and e["integrated"] and e["tested"]
        if not estrutural:
            cor = "VERMELHO"
        elif (e["e2e"] is False) or (e["observability"] is False):
            cor = "AMARELO"
        else:
            cor = "VERDE"
        cores[cor] += 1
        linhas.append((e, jornada, cor))

    def sn(v):
        return "n/a" if v is None else ("sim" if v else "não")

    out = ["# MOTOR COVERAGE MATRIX — IMPACTO TRUST (v0.27.0)", "",
           "Gerada por `scripts/make_motor_coverage_matrix.py` a partir de `impacto/engines/coverage.py` e das jornadas",
           "(`tests/demo_journeys.py`, `tests/test_e2e_*.py`). **Nenhuma coluna é escrita à mão.** Conferida por",
           "`backend/tests/test_v0270_release_docs.py`.", "",
           f"**{t['total']} motores** — VERDE {cores['VERDE']} · AMARELO {cores['AMARELO']} · VERMELHO {cores['VERMELHO']}.", "",
           "| Coluna | O que afirma |", "| --- | --- |",
           "| implementado | módulo importa e a função declarada é chamável |",
           "| integrado | rota no roteador ou chamada por tarefa agendada |",
           "| testado | alguma suíte importa o módulo ou exercita uma rota dele |",
           "| E2E | algum teste chama uma rota pelo HTTP (roteador, autorização, RLS, serialização) |",
           "| jornada | alguma rota do motor aparece numa jornada demo ou E2E de interface (n/a = sem rota própria) |",
           "| segurança | rotas exigem autenticação (pública só se revisada) |",
           "| rastro | auditoria, evento de domínio, Value Ledger, `ops_job_runs` ou versão persistida |",
           "| status | VERDE = tudo; AMARELO = sem E2E ou sem rastro; VERMELHO = falha estrutural |", "",
           "| motor | grupo | natureza | rotas | implementado | integrado | testado | E2E | jornada | segurança | rastro | status |",
           "| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for e, jornada, cor in sorted(linhas, key=lambda x: (x[0]["group"], x[0]["key"])):
        out.append(f"| `{e['key']}` — {e['name']} | {e['group']} | {e['kind']} | {len(e['routes'])} | {sn(e['implemented'])} | {sn(e['integrated'])} | "
                   f"{sn(e['tested'])} | {sn(e['e2e'])} | {sn(jornada)} | {sn(e['security'])} | {sn(e['observability'])} | {cor} |")
    out += ["", "## Motores AMARELOS e por quê", ""]
    amarelos = [(e, j) for e, j, c in linhas if c == "AMARELO"]
    if not amarelos:
        out.append("Nenhum.")
    for e, _ in amarelos:
        motivos = []
        if e["e2e"] is False:
            motivos.append("sem teste E2E pelo HTTP")
        if e["observability"] is False:
            motivos.append("sem rastro durável detectado (auditoria/evento/ledger/versão)")
        out.append(f"* `{e['key']}` — {'; '.join(motivos)}.")
    out += ["", "## Motores VERMELHOS", "", "Nenhum." if not cores["VERMELHO"] else "", ""]
    out.append("Nenhum motor é declarado 'completo' por descrição: a cor nasce das colunas, e as colunas nascem do código.")
    DEST.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{DEST.name}: {t['total']} motores · {cores}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
