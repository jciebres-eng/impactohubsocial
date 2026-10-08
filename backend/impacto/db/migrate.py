"""Runner de migrations forward-only com checksum e lock consultivo.

Uso:  python -m impacto.db.migrate            (usa MIGRATION_DATABASE_URL ou DATABASE_URL)
      python -m impacto.db.migrate --check    (falha se houver migrations pendentes ou alteradas)

Também sincroniza dados de REFERÊNCIA (não demo): catálogo de planos, feature flags e regras fiscais
candidatas em estado 'draft' (nunca aprovadas automaticamente).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from .pq import Connection, Json

BASE = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = BASE / "migrations"
CONFIG_DIR = BASE.parent / "config"
LOCK_ID = 726_431_001


def _files() -> list[Path]:
    return sorted(p for p in MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def _checksum(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def status(conn: Connection) -> dict:
    conn.execute_script(
        "CREATE TABLE IF NOT EXISTS schema_migrations(version text PRIMARY KEY, checksum char(64) NOT NULL,"
        " applied_at timestamptz NOT NULL DEFAULT now())"
    )
    applied = {r["version"]: r["checksum"] for r in conn.query("SELECT version, checksum FROM schema_migrations")}
    pending, changed = [], []
    for f in _files():
        v = f.stem
        if v not in applied:
            pending.append(v)
        elif applied[v] != _checksum(f):
            changed.append(v)
    return {"applied": sorted(applied), "pending": pending, "changed": changed}


def migrate(dsn: str, *, sync_reference: bool = True, upto: str | None = None, log=print) -> list[str]:
    """Aplica as migrations pendentes em ordem. `upto` para em uma versão (inclusive), o que permite preparar um banco
    em uma versão anterior e conferir o CAMINHO DE ATUALIZAÇÃO — e não só o banco criado do zero."""
    conn = Connection(dsn)
    done: list[str] = []
    try:
        conn.execute("SELECT pg_advisory_lock($1)", (LOCK_ID,))
        st = status(conn)
        if st["changed"]:
            raise RuntimeError(f"Migrations já aplicadas foram alteradas (forward-only): {st['changed']}")
        if upto and upto not in {f.stem for f in _files()}:
            raise RuntimeError(f"Migration '{upto}' não existe")
        for f in _files():
            if upto and f.stem > upto:
                break
            if f.stem not in st["pending"]:
                continue
            log(f"aplicando {f.name}")
            conn.execute_script("BEGIN;\n" + f.read_text(encoding="utf-8") + "\n;")
            conn.execute("INSERT INTO schema_migrations(version, checksum) VALUES ($1, $2)", (f.stem, _checksum(f)))
            conn.execute_script("COMMIT;")
            done.append(f.stem)
        if sync_reference:
            sync_reference_data(conn, log=log)
    except Exception:  # noqa: BLE001 - desfaz a migração em curso e RELANÇA (forward-only não aceita meio aplicado)
        try:
            conn.execute_script("ROLLBACK;")
        except Exception:  # noqa: S110 - rollback best-effort; a exceção original é relançada
            pass
        raise
    finally:
        try:
            conn.execute("SELECT pg_advisory_unlock($1)", (LOCK_ID,))
        finally:
            conn.close()
    return done


def sync_integration_providers(conn: Connection, log=print) -> int:
    """Catálogo de provedores do Integration Hub (config/integration_providers.json). Dado de referência, nunca demo.
    A maturidade do arquivo só pode REBAIXAR ou manter o que está no banco quando o banco já tiver evidência superior
    (sandbox/homologated/production_active promovidos pela administração não são desfeitos por deploy)."""
    path = CONFIG_DIR / "integration_providers.json"
    if not path.exists() or not conn.one("SELECT 1 FROM pg_tables WHERE tablename = 'integration_providers'"):
        return 0
    doc = json.loads(path.read_text(encoding="utf-8"))
    order = ["scaffolded", "contract_tested", "sandbox", "homologated", "production_active"]
    for p in doc["providers"]:
        cur = conn.one("SELECT maturity FROM integration_providers WHERE key = $1", p["key"])
        maturity = p["maturity"]
        if cur and order.index(cur["maturity"]) > order.index(maturity):
            maturity = cur["maturity"]
        conn.execute("INSERT INTO integration_providers(key, name, category, api_style, auth_kinds, capabilities, maturity, docs_url, notes, active, updated_at)"
                     " VALUES ($1,$2,$3,$4,$5::text[],$6::jsonb,$7,$8,$9,true, now()) ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name,"
                     " category = EXCLUDED.category, api_style = EXCLUDED.api_style, auth_kinds = EXCLUDED.auth_kinds, capabilities = EXCLUDED.capabilities,"
                     " maturity = EXCLUDED.maturity, docs_url = EXCLUDED.docs_url, notes = EXCLUDED.notes, updated_at = now()",
                     (p["key"], p["name"], p["category"], p["api_style"], p.get("auth_kinds", []), Json(p["capabilities"]), maturity,
                      p.get("docs_url"), p.get("notes")))
    return len(doc["providers"])


def sync_translations(conn: Connection, log=print) -> int:
    """Catálogo de traduções do núcleo (config/i18n.json). Dado de referência: pt-BR é a origem, en/es traduzem as
    MESMAS chaves. O que não estiver aqui continua em português na interface — a cobertura real fica em locales.coverage_note."""
    path = CONFIG_DIR / "i18n.json"
    if not path.exists() or not conn.one("SELECT 1 FROM pg_tables WHERE tablename = 'translations'"):
        return 0
    doc = json.loads(path.read_text(encoding="utf-8"))
    n = 0
    for locale, namespaces in doc["locales"].items():
        if not conn.one("SELECT 1 FROM locales WHERE code = $1", locale):
            continue
        for namespace, entries in namespaces.items():
            for key, value in entries.items():
                conn.execute("INSERT INTO translations(locale, namespace, key, value) VALUES ($1,$2,$3,$4)"
                             " ON CONFLICT (locale, namespace, key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
                             (locale, namespace, key, value))
                n += 1
    return n


def sync_reference_data(conn: Connection, log=print) -> None:
    plans = json.loads((CONFIG_DIR / "plans.json").read_text(encoding="utf-8"))
    conn.execute_script("BEGIN;")
    try:
        keys = []
        for key, p in plans["plans"].items():
            keys.append(key)
            conn.execute(
                # v0.27.0 (ADR-341): plano = pacote de capacidades, sem preço e sem periodicidade.
                "INSERT INTO plans(plan_key, version, role, name, limits, features, requires_flag, public, active, tier)"
                " VALUES ($1,$2,$3,$4,$5::jsonb,$6::text[],$7,$8,true,$9)"
                " ON CONFLICT (plan_key) DO UPDATE SET version=EXCLUDED.version, role=EXCLUDED.role, name=EXCLUDED.name, tier=EXCLUDED.tier,"
                " limits=EXCLUDED.limits,"
                " features=EXCLUDED.features, requires_flag=EXCLUDED.requires_flag, public=EXCLUDED.public, active=true",
                (key, plans["version"], p["role"], p["name"],
                 Json(p.get("limits", {})), p.get("features", []), p.get("requires_flag"), p.get("public", True), p.get("tier", "free")),
            )
        conn.execute("UPDATE plans SET active = false WHERE NOT (plan_key = ANY($1::text[]))", (keys,))
        for flag, cfg in plans.get("flags", {}).items():
            conn.execute(
                "INSERT INTO feature_flags(key, enabled, description) VALUES ($1,$2,$3) ON CONFLICT (key) DO NOTHING",
                (flag, bool(cfg["default"]), cfg.get("description")),
            )
        cand = CONFIG_DIR / "fiscal_rules.candidates.json"
        if cand.exists():
            for r in json.loads(cand.read_text(encoding="utf-8"))["rules"]:
                conn.execute(
                    "INSERT INTO fiscal_rules(code, version, name, mechanism, jurisdiction, taxpayer_types, taxpayer_regimes,"
                    " tax_base, limit_pct, combined_limit_group, limit_note, causes, requirements, project_requirements,"
                    " source_citation, source_url, notes, status)"
                    " VALUES ($1,$2,$3,$4,$5,$6::text[],$7::text[],$8,$9,$10,$11,$12::text[],$13::jsonb,$14::jsonb,$15,$16,$17,'draft')"
                    " ON CONFLICT (code, version) DO NOTHING",
                    (r["code"], r["version"], r["name"], r["mechanism"], r["jurisdiction"], r.get("taxpayer_types", ["pj"]),
                     r.get("taxpayer_regimes", []), r["tax_base"], r.get("limit_pct"), r.get("combined_limit_group"),
                     r.get("limit_note"), r.get("causes", []), Json(r.get("requirements", [])),
                     Json(r.get("project_requirements", [])), r["source_citation"], r.get("source_url"), r.get("notes")),
                )
        n_prov = sync_integration_providers(conn, log=log)
        n_tr = sync_translations(conn, log=log)
        conn.execute_script("COMMIT;")
        log(f"dados de referência sincronizados: {len(keys)} pacotes de capacidades (sem preço — ADR-341),"
            f" {n_prov} provedores de integração, {n_tr} traduções")
    except Exception:  # noqa: BLE001 - dado de referência é tudo-ou-nada; desfaz e RELANÇA
        conn.execute_script("ROLLBACK;")
        raise


def main(argv: list[str]) -> int:
    dsn = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        print("Defina MIGRATION_DATABASE_URL (papel impacto_owner)", file=sys.stderr)
        return 2
    if "--check" in argv:
        conn = Connection(dsn)
        try:
            st = status(conn)
        finally:
            conn.close()
        print(json.dumps(st))
        return 1 if (st["pending"] or st["changed"]) else 0
    migrate(dsn)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
