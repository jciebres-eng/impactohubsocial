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


def migrate(dsn: str, *, sync_reference: bool = True, log=print) -> list[str]:
    conn = Connection(dsn)
    done: list[str] = []
    try:
        conn.execute("SELECT pg_advisory_lock($1)", (LOCK_ID,))
        st = status(conn)
        if st["changed"]:
            raise RuntimeError(f"Migrations já aplicadas foram alteradas (forward-only): {st['changed']}")
        for f in _files():
            if f.stem not in st["pending"]:
                continue
            log(f"aplicando {f.name}")
            conn.execute_script("BEGIN;\n" + f.read_text(encoding="utf-8") + "\n;")
            conn.execute("INSERT INTO schema_migrations(version, checksum) VALUES ($1, $2)", (f.stem, _checksum(f)))
            conn.execute_script("COMMIT;")
            done.append(f.stem)
        if sync_reference:
            sync_reference_data(conn, log=log)
    except Exception:
        try:
            conn.execute_script("ROLLBACK;")
        except Exception:
            pass
        raise
    finally:
        try:
            conn.execute("SELECT pg_advisory_unlock($1)", (LOCK_ID,))
        finally:
            conn.close()
    return done


def sync_reference_data(conn: Connection, log=print) -> None:
    plans = json.loads((CONFIG_DIR / "plans.json").read_text(encoding="utf-8"))
    conn.execute_script("BEGIN;")
    try:
        keys = []
        for key, p in plans["plans"].items():
            keys.append(key)
            conn.execute(
                "INSERT INTO plans(plan_key, version, role, name, price_cents, interval, limits, features, requires_flag, public, active)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::text[],$9,$10,true)"
                " ON CONFLICT (plan_key) DO UPDATE SET version=EXCLUDED.version, role=EXCLUDED.role, name=EXCLUDED.name,"
                " price_cents=EXCLUDED.price_cents, interval=EXCLUDED.interval, limits=EXCLUDED.limits,"
                " features=EXCLUDED.features, requires_flag=EXCLUDED.requires_flag, public=EXCLUDED.public, active=true",
                (key, plans["version"], p["role"], p["name"], p.get("price_cents"), p.get("interval", "month"),
                 Json(p.get("limits", {})), p.get("features", []), p.get("requires_flag"), p.get("public", True)),
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
        conn.execute_script("COMMIT;")
        log(f"dados de referência sincronizados: {len(keys)} planos")
    except Exception:
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
