"""Gera FINAL_RELEASE_MANIFEST.json (FASE 52): versão, commit, data, arquivos, migrações, testes,
integrações, dependências externas, limitações conhecidas e situação do release — tudo lido do
repositório e dos artefatos gerados, nunca escrito à mão.

Uso: python3 scripts/make_final_release_manifest.py <commit> <status> <log-da-regressão>

v0.34.0 (E7): "migrações novas", "módulos de teste novos" e "documentos" estavam ESCRITOS À MÃO com os da v0.30.0 e
saíram assim nos manifestos da v0.31.0 à v0.34.0 (primeiro pacote). Agora são derivados: marca da versão no nome do
arquivo (0.34.0 → `v0340`) e os documentos que o próprio relatório cita entre crases.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    commit, status, log = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    version = (ROOT / "VERSION").read_text().strip()
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    migrations = sorted(p.name for p in (ROOT / "backend" / "migrations").glob("*.sql"))
    texto = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    # a execução COMPLETA mais recente do log é a que vale: o log guarda a 1ª passagem (com as falhas depois
    # corrigidas), a 2ª passagem completa e, ao fim, a reexecução só dos portões de fechamento (poucos testes).
    ms = re.findall(r"Ran (\d+) tests in ([\d.]+)s\s+(OK|FAILED)(?: \(([^)]*)\))?", texto)
    completas = [x for x in ms if int(x[0]) >= 1000]
    m = (completas or ms)[-1] if ms else None
    testes = {"total": int(m[0]), "seconds": float(m[1]), "result": m[2], "detail": m[3] or "", "runs_in_log": len(ms)} if m else None
    if testes and m in ms:
        # reexecuções DEPOIS da completa (módulos corrigidos e portões de fechamento): o resultado final não é só o da completa
        testes["after_full_run"] = [{"total": int(x[0]), "result": x[2], "detail": x[3] or ""}
                                    for x in ms[len(ms) - 1 - ms[::-1].index(m) + 1:]]
    with (ROOT / "docs" / "execution" / "INTEGRATION_HOMOLOGATION_MATRIX.csv").open(encoding="utf-8") as fh:
        integ = [{"provider": r["provider"], "capability": r["capability"], "state": r["state"], "credentials": r["credentials"]}
                 for r in csv.DictReader(fh)]
    report = (ROOT / "FINAL_EXECUTION_REPORT.md").read_text(encoding="utf-8")
    marca = "v" + "".join(version.split("."))          # 0.34.0 → v0340, como nos nomes de migração e de teste
    rastreados = set(files)
    novos_testes = sorted(f for f in files if re.match(rf"backend/tests/test_(e2e_)?{marca}_\w+\.py$", f))
    citados = []
    for ref in ["FINAL_EXECUTION_AUDIT.md", "RELEASE_NOTES.md", "CHANGELOG.md", "DECISIONS.md"] + \
            re.findall(r"`([\w./-]+\.(?:md|csv|xlsx|docx))`", report):
        for cand in (ref, f"docs/{ref}", f"docs/finance/{ref}", f"docs/execution/{ref}"):
            if cand in rastreados and cand not in citados:
                citados.append(cand)
                break
    def secao(n: int) -> str:
        m2 = re.search(rf"^## {n}\. .*?\n(.*?)(?=^## \d+\. )", report, re.DOTALL | re.MULTILINE)
        return m2.group(1).strip() if m2 else ""
    out = {
        "name": f"IMPACTO_TRUST_FINAL_RELEASE_{version}",
        "version": version, "commit": commit, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "release_status": status,
        "files": {"tracked_total": len(files), "traceability": f"IMPACTO_v{version}_TRACEABILITY.json",
                  "package": f"IMPACTO_TRUST_FINAL_RELEASE_{version}.zip"},
        "migrations": {"total": len(migrations), "last": migrations[-1], "new_in_this_version": [x for x in migrations if f"_{marca}_" in x]},
        "tests": testes,
        "new_test_modules": novos_testes,
        "integrations": integ,
        "external_dependencies": secao(25),
        "known_limitations": secao(26),
        "decision": secao(27),
        "documents": ["FINAL_EXECUTION_REPORT.md"] + [d for d in citados if d != "FINAL_EXECUTION_REPORT.md"],
    }
    (ROOT / "FINAL_RELEASE_MANIFEST.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"FINAL_RELEASE_MANIFEST.json: {version} @ {commit[:7]} — {status}; testes: {testes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
