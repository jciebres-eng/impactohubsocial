#!/usr/bin/env python3
"""Gera o release: RELEASE_MANIFEST.sha256 (compatível com `sha256sum -c`), RELEASE_MANIFEST.csv (sha256,arquivo,tamanho,data)
e FINAL_FULL_RELEASE.zip (sem ZIP aninhado, sem segredos, sem node_modules/caches/dados locais).

Uso:
  python3 scripts/make_release.py                 # gera manifesto + zip em ./dist-release/
  python3 scripts/make_release.py --verify DIR    # confere um diretório extraído contra RELEASE_MANIFEST.sha256
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist-release"
EXCLUDE_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv", "data", "dist-release", ".pytest_cache", ".ruff_cache",
                ".mypy_cache", "outbox", "android", "ios", "build",
                # dump de banco é DADO LOCAL (com dado de quem usou o ambiente): nunca entra no pacote
                "backups"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".log", ".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".jks", ".keystore", ".zip",
                  # despejo de banco em qualquer formato
                  ".dump", ".bak", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"}
EXCLUDE_NAMES = {".env", ".DS_Store", "RELEASE_MANIFEST.sha256", "RELEASE_MANIFEST.csv"}
# Exceções: evidência de teste (.log) é parte do release
KEEP_EXACT = {"docs/evidence/test_run_v0.17.0.log", "docs/evidence/ruff_v0.17.0.log",
              "docs/evidence/perf_v0.17.0.log",
              "docs/evidence/test_run_v0.16.0.log", "docs/evidence/ruff_v0.16.0.log",
              "docs/evidence/perf_v0.16.0.log", "history/v0.15.0/test_run_v0.15.0.log",
              "history/v0.15.0/VERSION",
              "docs/evidence/test_run_v0.15.0.log", "docs/evidence/ruff_v0.15.0.log", "docs/evidence/perf_v0.15.0.log", "history/v0.14.0/test_run_v0.14.0.log", "history/v0.14.0/VERSION", "docs/evidence/test_run_v0.14.0.log", "docs/evidence/ruff_v0.14.0.log", "history/v0.13.0/test_run_v0.13.0.log", "history/v0.13.0/VERSION", "docs/evidence/test_run_v0.13.0.log", "docs/evidence/ruff_v0.13.0.log", "history/v0.12.1/test_run_v0.12.1.log", "history/v0.12.1/VERSION", "docs/evidence/test_run_v0.12.1.log", "docs/evidence/ruff_v0.12.1.log", "history/v0.12.0/test_run_v0.12.0.log", "history/v0.12.0/VERSION", "docs/evidence/test_run_v0.12.0.log", "docs/evidence/ruff_v0.12.0.log", "history/v0.11.0/test_run_v0.11.0.log", "history/v0.11.0/VERSION", "docs/evidence/test_run_v0.7.0.log", "docs/evidence/test_run_v0.8.0.log", "docs/evidence/test_run_v0.9.0.log", "docs/evidence/test_run_v0.10.0.log", "docs/evidence/test_run_v0.10.1.log", "docs/evidence/test_run_v0.11.0.log", "docs/billing.md", "history/v0.10.1/VERSION", "history/v0.10.0/test_run_v0.10.0.log", "history/v0.10.1/test_run_v0.10.1.log", "history/v0.9.0/test_run_v0.9.0.log", "history/v0.8.0/test_run_v0.8.0.log", "history/v0.7.0/test_run_v0.7.0.log"}


def _tracked_evidence_log(rel) -> bool:
    """v0.27.0: toda evidência `.log` versionada em docs/evidence/ ou history/ faz parte do release — a lista
    fixa acima parou na v0.17.0 e os logs de regressão das versões seguintes ficavam fora do pacote."""
    return rel.suffix == ".log" and rel.parts[0] in ("docs", "history") and "evidence" in rel.parts or \
        (rel.suffix == ".log" and rel.parts[0] == "history")


SECRET_PATTERNS = [re.compile(p) for p in (
    r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----", r"AKIA[0-9A-Z]{16}", r"sk_live_[0-9a-zA-Z]{16,}", r"xox[baprs]-[0-9A-Za-z-]{10,}",
    r"ghp_[0-9A-Za-z]{30,}", r"sk-ant-[0-9A-Za-z_-]{20,}")]
REQUIRED = ["README.md", "FINAL_RELEASE_AUDIT.md", "RELEASE_NOTES.md", "CHANGELOG.md", "DEPLOYMENT_CHECKLIST.md", "PRODUCTION_READINESS.md",
            "SECURITY_AUDIT.md", "LGPD_AUDIT.md", "THIRD_PARTY_DEPENDENCIES.md", "IP_REGISTER.md", "CLAUDE_HANDOFF_FINAL.md", "ENVIRONMENT_SETUP.md",
            "DECISIONS.md", "VERSIONING.md", ".env.example", "VERSION",
            "SOLUTION_LIBRARY.md", "SOLUTION_SEARCH.md", "SOLUTION_MATCH_ENGINE.md", "REPLICATION_ENGINE.md", "INTENT_ENGINE.md", "AI_SEARCH_ARCHITECTURE.md",
            "SOLUTION_DATA_MODEL.md", "API_DOCUMENTATION.md", "TEST_REPORT.md", "docs/evidence/test_run_v0.9.0.log", "docs/evidence/search_perf_v0.9.0.json",
            "docs/evidence/weights_sensitivity_v0.9.0.json",
            "docs/evidence/test_run_v0.10.0.log", "docs/evidence/test_run_v0.10.1.log", "config/formalization_path.json", "history/v0.10.0/VERSION", "THIRD_SECTOR_MODEL.md", "INSTITUTIONAL_ELIGIBILITY_ENGINE.md", "FISCAL_RULE_ENGINE.md", "MATCH_ENGINE.md",
            "REPOSITORY_PROJECTS.md", "DATABASE_SCHEMA.md", "config/institutional_rules.candidates.json", "history/v0.9.0/VERSION",
            "KNOWLEDGE_HUB.md", "USER_GUIDES.md", "TRAINING_ACADEMY.md", "SUPPORT_SYSTEM.md", "PARTNERSHIP_SYSTEM.md", "TRIAL_SYSTEM.md", "CONTENT_GOVERNANCE.md",
            "KNOWLEDGE_DATA_MODEL.md", "STORE_READINESS.md", "docs/evidence/test_run_v0.12.0.log", "docs/evidence/ruff_v0.12.0.log", "history/v0.11.0/VERSION",
            "config/help_synonyms.json", "config/onboarding_paths.json", "backend/migrations/0009_v0120_knowledge_hub.sql",
            "FINAL_TECHNICAL_BASELINE.md", "DESIGN_HANDOFF.md", "FINAL_RELEASE_MANIFEST.json", "backend/migrations/0010_v0121_indexes.sql",
            "docs/evidence/test_run_v0.12.1.log", "docs/evidence/ruff_v0.12.1.log", "history/v0.12.0/VERSION",
            "backend/tests/test_v0120_hardening.py", "backend/tests/test_e2e_baseline.py",
            "INTEGRATION_INVENTORY.md", "INTEGRATION_ARCHITECTURE.md", "INTEGRATION_HUB.md", "INTEGRATION_SECURITY.md",
            "INTEGRATION_OPERATIONS.md", "INTEGRATION_TESTING.md", "INTEGRATION_PROVIDER_GUIDE.md",
            "INTEGRATION_CAPABILITY_MATRIX.md", "FINAL_INTEGRATION_HARDENING_REPORT.md", "FINAL_INTEGRATION_MANIFEST.json",
            "backend/migrations/0011_v0130_integration_hub.sql", "backend/tests/test_v0130_integrations.py",
            "config/integration_providers.json", "docs/evidence/test_run_v0.13.0.log", "docs/evidence/ruff_v0.13.0.log",
            "history/v0.12.1/VERSION",
            "TRUST_INVENTORY.md", "TRUST_ARCHITECTURE.md", "TRUST_IDENTITY.md", "DIGITAL_SIGNATURE.md",
            "PUBLIC_VERIFICATION.md", "TRUST_SECURITY.md", "TRUST_TESTING.md", "SDG_ESG_TAXONOMY.md", "I18N.md",
            "DOCUMENT_FORMATS.md", "FINAL_TRUST_HARDENING_REPORT.md", "FINAL_TRUST_MANIFEST.json",
            "backend/migrations/0012_v0140_trust_layer.sql", "backend/tests/test_v0140_trust.py",
            "backend/tests/test_e2e_v0140_trust.py", "config/i18n.json",
            "docs/evidence/test_run_v0.14.0.log", "docs/evidence/ruff_v0.14.0.log", "history/v0.13.0/VERSION",
            # v0.15.0 — núcleo do produto
            "CORE_PRODUCT_ARCHITECTURE.md", "MATCH_ENGINE_FINAL.md", "DIAGNOSTIC_ENGINE.md", "PROJECT_LIFECYCLE.md",
            "DOCUMENT_ASSEMBLY.md", "LONGITUDINAL_TRACKING.md", "KEY_ROTATION.md", "SIGNATURE_VALIDATION_MATRIX.md",
            "EXTERNAL_DEPENDENCIES.md", "HOMOLOGATION_MATRIX.md", "DATA_RETENTION_MATRIX.md",
            "DATABASE_INTEGRITY_REPORT.md", "SECURITY_FINAL_CHECKLIST.md", "PERFORMANCE_REPORT.md",
            "RELEASE_READINESS.md", "FINAL_PRE_DESIGN_HARDENING_REPORT.md", "PRE_DESIGN_AUDIT.md",
            "V0.15.0_FINAL_MANIFEST.json",
            "backend/migrations/0013_v0150_core_product.sql", "backend/migrations/0014_v0150_platform_templates.sql",
            "backend/migrations/0015_v0150_fk_indexes.sql",
            "backend/impacto/core/evidence.py", "backend/impacto/core/lifecycle.py",
            "backend/impacto/core/diagnostic.py", "backend/impacto/core/assembly.py", "backend/impacto/core/keys.py",
            "backend/impacto/api/lifecycle_routes.py", "backend/impacto/api/diagnostic_routes.py",
            "backend/impacto/api/assembly_routes.py", "backend/impacto/api/core_schemas.py",
            "backend/tests/test_v0150_core.py", "backend/tests/test_v0150_invariants.py",
            "backend/tests/test_v0150_security.py", "backend/tests/test_v0150_upgrade.py",
            "backend/tests/test_v0150_performance.py", "backend/tests/test_e2e_v0150_journeys.py",
            "backend/tests/test_e2e_v0150_web.py", "web/src/pages/core.tsx",
            "scripts/db_integrity_report.py",
            "docs/evidence/test_run_v0.15.0.log", "docs/evidence/ruff_v0.15.0.log",
            "docs/evidence/perf_v0.15.0.log", "docs/evidence/db_integrity_v0.15.0.txt",
            "history/v0.14.0/VERSION",
            # v0.16.0 — IMPACT NETWORK CORE
            "IMPACT_NETWORK_ARCHITECTURE.md", "IMPACT_GRAPH.md", "RELATIONSHIP_MODEL.md", "PROPOSAL_ENGINE.md",
            "IMPACT_MARKETPLACE.md", "MESSAGING_ARCHITECTURE.md", "NOTIFICATION_ARCHITECTURE.md",
            "IMPACT_REPORTING.md", "ROLE_BASED_EXPERIENCE.md", "WORKSPACE_ARCHITECTURE.md",
            "PRIVACY_VISIBILITY_MATRIX.md", "MODERATION_LADDER.md", "BILLING_V2.md",
            "INFORMATION_ARCHITECTURE.md", "NAVIGATION_MODEL.md", "DESIGN_HANDOFF_FINAL.md",
            "MOBILE_READINESS_FINAL.md", "FINAL_IMPACT_NETWORK_HARDENING_REPORT.md",
            "V0.16.0_FINAL_MANIFEST.json",
            "backend/migrations/0016_v0160_impact_network.sql", "backend/migrations/0017_v0160_billing_v2.sql",
            "backend/impacto/clock.py",
            "backend/impacto/network/__init__.py", "backend/impacto/network/relationships.py",
            "backend/impacto/network/proposals.py", "backend/impacto/network/marketplace.py",
            "backend/impacto/network/messaging.py", "backend/impacto/network/notify.py",
            "backend/impacto/network/events.py", "backend/impacto/network/readiness.py",
            "backend/impacto/network/recommendation.py", "backend/impacto/network/profiles.py",
            "backend/impacto/network/impact_report.py", "backend/impacto/network/workspace.py",
            "backend/impacto/network/enforcement.py",
            "backend/impacto/api/network_schemas.py", "backend/impacto/api/network_core_routes.py",
            "backend/impacto/api/network_hub_routes.py",
            "backend/tests/test_v0160_network.py", "backend/tests/test_v0160_invariants.py",
            "backend/tests/test_e2e_v0160_journeys.py",   # v0.27.0 (ADR-341): test_v0160_billing.py saiu com services/billing.py
            "scripts/sql_prepare_check.py",
            "web/src/pages/workspace.tsx", "web/src/pages/net.tsx", "web/src/pages/market.tsx",
            "web/src/pages/talk.tsx", "web/src/pages/impactreport.tsx", "web/src/pages/publicprofile.tsx",
            "web/src/pages/territory.tsx", "web/src/pages/moderation.tsx",
            "docs/evidence/test_run_v0.16.0.log", "docs/evidence/ruff_v0.16.0.log",
            "docs/evidence/perf_v0.16.0.log", "docs/evidence/db_integrity_v0.16.0.txt",
            "history/v0.15.0/VERSION",
            # v0.17.0 — camada econômica, legal e de pagamento
            "ECONOMICS.md", "PROGRAM_ARCHITECTURE.md", "VALUE_LEDGER.md", "MONETIZATION.md",
            "PAYMENT_ARCHITECTURE.md", "MONETIZATION_LEGAL_MATRIX.md", "SAAS_ECONOMIC_AUDIT.md",
            "FINAL_ECONOMIC_HARDENING_REPORT.md", "docs/LEGAL_FRAMEWORK.md", "docs/AI_ENGINES.md",
            "docs/legal/SUBSCRIPTION.md", "docs/legal/MARKETPLACE.md", "docs/legal/INTERMEDIATION.md",
            "docs/legal/PAYMENT.md", "docs/legal/CANCELLATION.md", "docs/legal/REFUND.md",
            "docs/legal/B2B.md", "docs/legal/B2G.md",
            "backend/migrations/0018_v0170_programs.sql", "backend/migrations/0019_v0170_value_ledger.sql",
            "backend/migrations/0020_v0170_monetization.sql", "backend/migrations/0021_v0170_legal_cards.sql",
            "backend/migrations/0022_v0170_payments.sql", "backend/migrations/0023_v0170_legal.sql",
            "backend/migrations/0024_v0170_privacy_hardening.sql",
            "backend/impacto/economics/programs.py", "backend/impacto/economics/value_ledger.py",
            "backend/impacto/economics/billable.py", "backend/impacto/economics/payments.py",
            "backend/impacto/services/legal.py", "backend/impacto/engines/registry.py",
            "backend/impacto/api/program_routes.py", "backend/impacto/api/legal_routes.py",
            "backend/tests/test_v0170_programs.py", "backend/tests/test_v0170_value.py",
            "backend/tests/test_v0170_monetization.py", "backend/tests/test_v0170_payments.py",
            "backend/tests/test_v0170_legal.py", "backend/tests/test_v0170_security.py",
            "backend/tests/test_v0170_engines.py", "backend/tests/test_v0170_docs.py",
            "scripts/gen_legal_registry.py",
            "docs/evidence/test_run_v0.17.0.log", "docs/evidence/ruff_v0.17.0.log",
            "docs/evidence/perf_v0.17.0.log", "docs/evidence/db_integrity_v0.17.0.txt",
            "history/v0.16.0/VERSION",
            # v0.27.0 — saídas exigidas pelo PROMPT MASTER (ADR-341)
            "FINAL_EXECUTION_AUDIT.md", "FINAL_EXECUTION_REPORT.md", "MOTOR_COVERAGE_MATRIX.md", "EXTERNAL_INTEGRATIONS.md",
            "24_MONTH_FINANCIAL_MODEL.md", "docs/ECONOMIC_MODEL.md", "docs/execution/SUBSCRIPTION_INVENTORY.md",
            "config/economic_model.json", "backend/migrations/0067_v0270_no_subscription.sql",
            "backend/tests/test_v0270_no_subscription.py", "backend/tests/test_v0270_economy.py",
            "backend/tests/test_v0270_financial_model.py", "backend/tests/test_v0270_release_docs.py",
            "docs/evidence/test_run_v0.27.0.log", "history/v0.26.0/VERSION"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect() -> list[Path]:
    files = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if rel.as_posix() in KEEP_EXACT or _tracked_evidence_log(rel):
            files.append(p)
            continue
        if set(rel.parts[:-1]) & EXCLUDE_DIRS and not (rel.parts[0] == "web" and rel.parts[1] == "dist") \
                and not rel.as_posix().startswith("web/brand/mobile/"):
            # `android`/`ios` na lista são os PROJETOS gerados pelo Capacitor (web/android, web/ios);
            # os ícones oficiais da identidade moram em web/brand/mobile/{android,ios} e são FONTE —
            # a v0.24.0 descobriu que a exclusão por nome os deixava fora do pacote.
            continue
        if p.name in EXCLUDE_NAMES or p.suffix in EXCLUDE_SUFFIX:
            continue
        files.append(p)
    return files


def scan_secrets(files: list[Path]) -> list[str]:
    hits = []
    for p in files:
        if p.stat().st_size > 5_000_000:
            continue
        try:
            text = p.read_text("utf-8", errors="ignore").replace("AKIA" + "IOSFODNN7EXAMPLE", "")   # chave de EXEMPLO pública da documentação AWS (vetor SigV4)
        except OSError:
            continue
        for rx in SECRET_PATTERNS:
            if rx.search(text):
                hits.append(f"{p.relative_to(ROOT)}: {rx.pattern}")
    return hits


def build(zip_name: str = "FINAL_FULL_RELEASE.zip") -> int:
    version = (ROOT / "VERSION").read_text().strip()
    files = collect()
    missing = [r for r in REQUIRED if not (ROOT / r).exists()]
    if missing:
        print("Arquivos obrigatórios ausentes:", ", ".join(missing), file=sys.stderr)
        return 2
    if not (ROOT / "web/dist/index.html").exists():
        print("web/dist ausente — rode `make web` antes.", file=sys.stderr)
        return 2
    nested = [p for p in ROOT.rglob("*.zip") if "node_modules" not in p.parts and "dist-release" not in p.parts]
    if nested:
        print("ZIP aninhado encontrado (proibido):", nested, file=sys.stderr)
        return 2
    hits = scan_secrets(files)
    if hits:
        print("Possíveis segredos encontrados — release abortado:\n  " + "\n  ".join(hits), file=sys.stderr)
        return 2
    OUT.mkdir(exist_ok=True)
    rows = []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        st = p.stat()
        rows.append((sha256(p), rel, st.st_size, dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
    manifest = "".join(f"{h}  {rel}\n" for h, rel, _, _ in rows)
    (ROOT / "RELEASE_MANIFEST.sha256").write_text(manifest)
    with (ROOT / "RELEASE_MANIFEST.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sha256", "file", "size_bytes", "mtime_utc"])
        w.writerows(rows)
    top = f"plataforma-impacto-v{version}"
    zpath = OUT / zip_name
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files + [ROOT / "RELEASE_MANIFEST.sha256", ROOT / "RELEASE_MANIFEST.csv"]:
            z.write(p, f"{top}/{p.relative_to(ROOT).as_posix()}")
    zsha = sha256(zpath)
    (OUT / f"{zip_name}.sha256").write_text(f"{zsha}  {zip_name}\n")
    print(f"{len(files)} arquivos · zip {zpath.stat().st_size / 1e6:.2f} MB · sha256 {zsha}")
    return 0


def verify(d: Path) -> int:
    mf = d / "RELEASE_MANIFEST.sha256"
    if not mf.exists():
        print("RELEASE_MANIFEST.sha256 não encontrado em", d, file=sys.stderr)
        return 2
    bad = 0
    listed = set()
    for line in mf.read_text().splitlines():
        h, rel = line.split("  ", 1)
        listed.add(rel)
        p = d / rel
        if not p.exists():
            print("FALTA ", rel)
            bad += 1
        elif sha256(p) != h:
            print("DIFERE", rel)
            bad += 1
    zips = [p for p in d.rglob("*.zip")]
    if zips:
        print("ZIP aninhado:", zips)
        bad += 1
    print(f"{len(listed)} arquivos verificados · {'OK' if not bad else f'{bad} problema(s)'}")
    return 1 if bad else 0


USO = """Uso:
  make_release.py                      constrói o pacote com o nome padrão
  make_release.py --name ARQUIVO.zip   constrói com o nome dado
  make_release.py --verify DIRETORIO   confere um pacote extraído contra RELEASE_MANIFEST.sha256
"""

if __name__ == "__main__":
    # ARGUMENTO DESCONHECIDO RECUSA, não constrói.
    #
    # A versão anterior caía no `build()` final para qualquer argumento não reconhecido — inclusive
    # `--help`. Um auditor independente rodou `make_release.py --help` para ver a sintaxe e o script
    # EMPACOTOU: reescreveu `RELEASE_MANIFEST.csv` e `.sha256` versionados e criou um ZIP novo em
    # `dist-release/`. Construir release é efeito colateral grande demais para ser o comportamento
    # padrão de um comando digitado errado.
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help", "help"):
        print(USO)
        sys.exit(0)
    if args and args[0] == "--verify":
        if len(args) < 2:
            sys.exit("--verify exige o diretório do pacote extraído\n\n" + USO)
        sys.exit(verify(Path(args[1])))
    if args and args[0] == "--name":
        if len(args) < 2:
            sys.exit("--name exige o nome do arquivo\n\n" + USO)
        sys.exit(build(args[1]))
    if args:
        sys.exit(f"argumento não reconhecido: {args[0]}\n\n" + USO)
    sys.exit(build())
