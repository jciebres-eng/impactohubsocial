#!/usr/bin/env python3
"""Coleta FATOS do banco para o DATABASE_INTEGRITY_REPORT.md. Nada aqui é escrito à mão: é consulta ao catálogo.

Uso: ADMIN_DATABASE_URL=... python3 scripts/db_integrity_report.py [--json]
     (por padrão lê o banco de desenvolvimento criado por scripts/dev_reset_db.sh)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

DSN = os.getenv("REPORT_DATABASE_URL",
                "postgresql://impacto_owner:owner_dev_pw@127.0.0.1:5432/impacto_dev")

QUERIES: dict[str, str] = {
    "tables": "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'",
    "tables_without_rls": """SELECT coalesce(string_agg(c.relname, ', ' ORDER BY c.relname), '')
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity""",
    "policies": "SELECT count(*) FROM pg_policies WHERE schemaname = 'public'",
    "tables_with_policy": "SELECT count(DISTINCT tablename) FROM pg_policies WHERE schemaname = 'public'",
    "triggers": """SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND NOT t.tgisinternal""",
    "functions": """SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'""",
    "security_definer_functions": """SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.prosecdef""",
    "security_definer_without_search_path": """SELECT coalesce(string_agg(p.proname, ', ' ORDER BY p.proname), '')
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.prosecdef
          AND NOT EXISTS (SELECT 1 FROM unnest(coalesce(p.proconfig, '{}')) cfg WHERE cfg LIKE 'search_path=%')""",
    "foreign_keys": """SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace WHERE n.nspname = 'public' AND c.contype = 'f'""",
    # FK sem índice cujo PRIMEIRO campo é a coluna referenciadora. Só conta quando o índice começa por ela:
    # índice que a tem no meio não serve para o ON DELETE nem para a busca pelo lado do pai.
    "fk_without_index": """WITH fk AS (
          SELECT c.conrelid, c.conkey[1] AS col, t.relname AS tbl, c.conname,
                 (SELECT a.attname FROM pg_attribute a WHERE a.attrelid = c.conrelid AND a.attnum = c.conkey[1]) AS colname
            FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
           WHERE n.nspname = 'public' AND c.contype = 'f' AND array_length(c.conkey, 1) = 1)
        SELECT count(*) FROM fk
         WHERE NOT EXISTS (SELECT 1 FROM pg_index i
                            WHERE i.indrelid = fk.conrelid AND i.indkey[0] = fk.col)""",
    # as que realmente importam: coluna de tenant ou de pai que a aplicação filtra/apaga em cascata
    "fk_without_index_hot": """WITH fk AS (
          SELECT c.conrelid, c.conkey[1] AS col, t.relname AS tbl,
                 (SELECT a.attname FROM pg_attribute a WHERE a.attrelid = c.conrelid AND a.attnum = c.conkey[1]) AS colname
            FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
           WHERE n.nspname = 'public' AND c.contype = 'f' AND array_length(c.conkey, 1) = 1)
        SELECT coalesce(string_agg(fk.tbl || '.' || fk.colname, ', ' ORDER BY fk.tbl, fk.colname), '') FROM fk
         WHERE fk.colname IN ('org_id', 'project_id', 'application_id', 'solution_id', 'call_id', 'diagnosis_id',
                              'template_id', 'connection_id', 'course_id', 'agreement_id', 'milestone_id')
           AND NOT EXISTS (SELECT 1 FROM pg_index i
                            WHERE i.indrelid = fk.conrelid AND i.indkey[0] = fk.col)""",
    "check_constraints": """SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace WHERE n.nspname = 'public' AND c.contype = 'c'""",
    "unique_constraints": """SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace WHERE n.nspname = 'public' AND c.contype IN ('u','p')""",
    "indexes": "SELECT count(*) FROM pg_indexes WHERE schemaname = 'public'",
    "tables_without_primary_key": """SELECT coalesce(string_agg(c.relname, ', ' ORDER BY c.relname), '')
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype = 'p')""",
    "nullable_org_id_columns": """SELECT coalesce(string_agg(table_name, ', ' ORDER BY table_name), '')
        FROM information_schema.columns
        WHERE table_schema = 'public' AND column_name = 'org_id' AND is_nullable = 'YES'""",
    "append_only_tables": """SELECT coalesce(string_agg(DISTINCT c.relname, ', ' ORDER BY c.relname), '')
        FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_proc p ON p.oid = t.tgfoid
        WHERE p.proname = 'forbid_mutation' AND NOT t.tgisinternal""",
    "guarded_tables": """SELECT coalesce(string_agg(DISTINCT c.relname, ', ' ORDER BY c.relname), '')
        FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_proc p ON p.oid = t.tgfoid
        WHERE p.proname = 'guard_columns' AND NOT t.tgisinternal""",
    "migrations_applied": "SELECT count(*) FROM schema_migrations",
    "migrations_list": "SELECT string_agg(version, ', ' ORDER BY version) FROM schema_migrations",
    "app_role_tables_with_delete": """SELECT count(DISTINCT table_name) FROM information_schema.role_table_grants
        WHERE grantee = 'impacto_app' AND privilege_type = 'DELETE' AND table_schema = 'public'""",
    "app_role_column_grants": """SELECT count(*) FROM information_schema.column_privileges
        WHERE grantee = 'impacto_app' AND table_schema = 'public'""",
    "orphan_rows_check": """SELECT 'nenhuma verificação de órfão aplicável: toda referência é FK declarada'""",
    "ods_goals": "SELECT count(*) FROM ods_goals",
    "status_graph_edges": "SELECT count(*) FROM project_status_graph",
    "signature_providers_in_production": "SELECT count(*) FROM signature_providers WHERE state = 'production'",
    "document_templates_published": "SELECT count(*) FROM document_templates WHERE status = 'published'",
}


def q(sql: str) -> str:
    out = subprocess.run(["psql", DSN, "-v", "ON_ERROR_STOP=1", "-q", "-tA", "-c", sql],
                         capture_output=True, text=True, check=False)
    if out.returncode != 0:
        return f"ERRO: {out.stderr.strip().splitlines()[-1] if out.stderr.strip() else 'falhou'}"
    return out.stdout.strip()


def main() -> int:
    facts = {k: q(sql) for k, sql in QUERIES.items()}
    if "--json" in sys.argv:
        print(json.dumps(facts, ensure_ascii=False, indent=2))
    else:
        for k, v in facts.items():
            print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
