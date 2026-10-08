"""Gera FINAL_RELEASE_MANIFEST.json (FASE 52): versão, commit, data, arquivos, migrações, testes,
integrações, dependências externas, limitações conhecidas e situação do release — tudo lido do
repositório e dos artefatos gerados, nunca escrito à mão.

Uso: python3 scripts/make_final_release_manifest.py <commit> <status> <log-da-regressão>
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
    # a ÚLTIMA execução do log é a que vale (o log guarda a 1ª passagem, com as falhas corrigidas, e a 2ª)
    ms = re.findall(r"Ran (\d+) tests in ([\d.]+)s\s+(OK|FAILED)(?: \(([^)]*)\))?", texto)
    m = ms[-1] if ms else None
    testes = {"total": int(m[0]), "seconds": float(m[1]), "result": m[2], "detail": m[3] or "", "runs_in_log": len(ms)} if m else None
    with (ROOT / "docs" / "execution" / "INTEGRATION_HOMOLOGATION_MATRIX.csv").open(encoding="utf-8") as fh:
        integ = [{"provider": r["provider"], "capability": r["capability"], "state": r["state"], "credentials": r["credentials"]}
                 for r in csv.DictReader(fh)]
    report = (ROOT / "FINAL_EXECUTION_REPORT.md").read_text(encoding="utf-8")
    def secao(n: int) -> str:
        m2 = re.search(rf"^## {n}\. .*?\n(.*?)(?=^## \d+\. )", report, re.DOTALL | re.MULTILINE)
        return m2.group(1).strip() if m2 else ""
    out = {
        "name": f"IMPACTO_TRUST_FINAL_RELEASE_{version}",
        "version": version, "commit": commit, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "release_status": status,
        "files": {"tracked_total": len(files), "traceability": f"IMPACTO_v{version}_TRACEABILITY.json",
                  "package": f"IMPACTO_TRUST_FINAL_RELEASE_{version}.zip"},
        "migrations": {"total": len(migrations), "last": migrations[-1], "new_in_this_version": [x for x in migrations if "v0260" in x]},
        "tests": testes,
        "new_test_modules": ["backend/tests/test_v0260_contract_rules.py", "backend/tests/test_v0260_control_towers.py"],
        "integrations": integ,
        "external_dependencies": secao(25),
        "known_limitations": secao(26),
        "decision": secao(27),
        "documents": ["FINAL_EXECUTION_REPORT.md", "FINAL_EXECUTION_AUDIT.md", "RELEASE_NOTES.md",
                      "docs/execution/TECHNICAL_BASELINE_BEFORE_EXECUTION.md", "docs/execution/SYSTEM_INTEGRATION_MATRIX.md"],
    }
    (ROOT / "FINAL_RELEASE_MANIFEST.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"FINAL_RELEASE_MANIFEST.json: {version} @ {commit[:7]} — {status}; testes: {testes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
