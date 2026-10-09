#!/usr/bin/env python3
"""Contas de DEMONSTRAÇÃO num banco que não é de demonstração (v0.32.0) — listar, desativar, reativar.

Decisão do responsável (09/10/2026): a produção começa limpa; as 15 contas `@demo.impacto.local` que
estão no banco de produção são DESATIVADAS (não apagadas). Faz o MESMO que a tela de administração faz
(`admin_routes`): `users.status = 'disabled'`, sessões encerradas com `admin_disabled`, evento
`admin.user_status` na trilha de auditoria; organizações cujos membros são TODOS de demonstração vão
para `suspended` com `admin.org_status`. A organização da plataforma nunca é tocada (a conta real de
administração também é membro dela).

Modos:
  listar     somente leitura (transação READ ONLY): contas, organizações e conteúdo público delas.
  desativar  exige CONFIRMACAO="DESATIVAR CONTAS DEMO"; uma transação só (tudo ou nada).
  reativar   exige CONFIRMACAO="REATIVAR CONTAS DEMO"; desfaz o estado (as sessões encerradas não voltam:
             quem entrar de novo faz login).

Lê DATABASE_URL (conexão administrativa). Nunca imprime senha nem dado de conta real: só contagens e os
e-mails fictícios `@demo.impacto.local`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from impacto.db.pq import Connection  # noqa: E402

DOMINIO = "%@demo.impacto.local"
MOTIVO = "Conta de demonstração no banco de produção — desativada por decisão do responsável (09/10/2026)"

#: Conteúdo que aparece para o público, por tabela: (tabela, coluna da organização, coluna de estado,
#: valor "publicado", valor "fora do ar"). As listagens públicas não filtram organização suspensa — então
#: `desativar` tira esse conteúdo do ar, guarda cada id na auditoria, e `reativar` devolve exatamente esses.
CONTEUDO = [
    ("projects", "org_id", "visibility", "published", "private"),
    ("solutions", "org_id", "visibility", "published", "archived"),
    ("materials", "org_id", "status", "published", "archived"),
    ("calls", "owner_org_id", "status", "open", "suspended"),
]


def _orgs_so_demo(c) -> list[dict]:
    return c.query(
        "SELECT o.id::text AS id, o.kind, o.legal_name, o.status FROM organizations o"
        " WHERE o.kind <> 'platform'"
        "   AND EXISTS (SELECT 1 FROM memberships m WHERE m.org_id = o.id)"
        "   AND NOT EXISTS (SELECT 1 FROM memberships m JOIN users u ON u.id = m.user_id"
        "                   WHERE m.org_id = o.id AND u.email::text NOT LIKE $1)"
        " ORDER BY o.legal_name", DOMINIO)


def _existe(c, tabela: str, coluna: str) -> bool:
    return bool(c.scalar("SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'"
                         " AND table_name = $1 AND column_name = $2", tabela, coluna))


def listar(c) -> dict:
    contas = c.query("SELECT email::text AS email, status, is_platform_admin FROM users WHERE email::text LIKE $1 ORDER BY email", DOMINIO)
    reais = c.scalar("SELECT count(*) FROM users WHERE email::text NOT LIKE $1", DOMINIO)
    orgs = _orgs_so_demo(c)
    ids = [o["id"] for o in orgs]
    sessoes = c.scalar("SELECT count(*) FROM sessions s JOIN users u ON u.id = s.user_id"
                       " WHERE u.email::text LIKE $1 AND s.revoked_at IS NULL", DOMINIO)
    conteudo = {}
    for tabela, col_org, col, pub, _oculto in CONTEUDO:
        if ids and _existe(c, tabela, col_org):
            conteudo[tabela] = c.scalar(f"SELECT count(*) FROM {tabela} WHERE {col_org}::text = ANY($1::text[]) AND {col} = $2", ids, pub)  # noqa: S608 - nomes fixos acima
    return {"contas_demo": contas, "contas_reais": reais, "orgs_so_demo": orgs, "sessoes_abertas_demo": sessoes,
            "conteudo_publico_das_orgs_demo": conteudo}


def desativar(c) -> dict:
    users = c.query("SELECT id::text AS id FROM users WHERE email::text LIKE $1 AND status = 'active'", DOMINIO)
    orgs = [o for o in _orgs_so_demo(c) if o["status"] == "active"]
    for u in users:
        c.run("UPDATE users SET status = 'disabled', updated_at = now() WHERE id = $1", u["id"])
        c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = 'admin_disabled' WHERE user_id = $1 AND revoked_at IS NULL", u["id"])
        c.run("INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, payload)"
              " VALUES (NULL, NULL, 'admin.user_status', 'user', $1::text, $2::jsonb)",
              u["id"], json.dumps({"status": "disabled", "reason": MOTIVO, "via": "scripts/demo_accounts.py"}))
    for o in orgs:
        c.run("UPDATE organizations SET status = 'suspended' WHERE id = $1", o["id"])
        c.run("INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, payload)"
              " VALUES ($1::uuid, NULL, 'admin.org_status', 'organization', $1::text, $2::jsonb)",
              o["id"], json.dumps({"status": "suspended", "reason": MOTIVO, "via": "scripts/demo_accounts.py"}))
    ids = [o["id"] for o in _orgs_so_demo(c)]
    fora = 0
    for tabela, col_org, col, pub, oculto in CONTEUDO:
        if not ids or not _existe(c, tabela, col_org):
            continue
        linhas = c.query(f"SELECT id::text AS id, {col_org}::text AS org_id FROM {tabela}"  # noqa: S608 - nomes fixos acima
                         f" WHERE {col_org}::text = ANY($1::text[]) AND {col} = $2", ids, pub)
        for r in linhas:
            c.run(f"UPDATE {tabela} SET {col} = $2 WHERE id = $1", r["id"], oculto)  # noqa: S608
            c.run("INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, payload)"
                  " VALUES ($1::uuid, NULL, 'admin.content_visibility', $2, $3::text, $4::jsonb)",
                  r["org_id"], tabela, r["id"], json.dumps({"column": col, "from": pub, "to": oculto, "reason": MOTIVO,
                                                             "via": "scripts/demo_accounts.py"}))
        fora += len(linhas)
    return {"contas_desativadas": len(users), "orgs_suspensas": len(orgs), "conteudo_tirado_do_ar": fora}


def reativar(c) -> dict:
    users = c.query("SELECT id::text AS id FROM users WHERE email::text LIKE $1 AND status = 'disabled'", DOMINIO)
    orgs = [o for o in _orgs_so_demo(c) if o["status"] == "suspended"]
    for u in users:
        c.run("UPDATE users SET status = 'active', updated_at = now() WHERE id = $1", u["id"])
        c.run("INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, payload)"
              " VALUES (NULL, NULL, 'admin.user_status', 'user', $1::text, $2::jsonb)",
              u["id"], json.dumps({"status": "active", "reason": "reativação de conta de demonstração", "via": "scripts/demo_accounts.py"}))
    for o in orgs:
        c.run("UPDATE organizations SET status = 'active' WHERE id = $1", o["id"])
        c.run("INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, payload)"
              " VALUES ($1::uuid, NULL, 'admin.org_status', 'organization', $1::text, $2::jsonb)",
              o["id"], json.dumps({"status": "active", "reason": "reativação de organização de demonstração", "via": "scripts/demo_accounts.py"}))
    volta = 0
    for tabela, _col_org, col, pub, oculto in CONTEUDO:
        if not _existe(c, tabela, "id"):
            continue
        ids = [r["id"] for r in c.query(
            "SELECT DISTINCT object_id AS id FROM audit_events WHERE action = 'admin.content_visibility' AND object_type = $1"
            " AND payload->>'via' = 'scripts/demo_accounts.py' AND payload->>'to' = $2", tabela, oculto)]
        if ids:
            volta += c.run(f"UPDATE {tabela} SET {col} = $2 WHERE id::text = ANY($1::text[]) AND {col} = $3", ids, pub, oculto)  # noqa: S608
    return {"contas_reativadas": len(users), "orgs_reativadas": len(orgs), "conteudo_devolvido": volta}


def _imprime(titulo: str, d: dict) -> None:
    print(f"## {titulo}")
    print(json.dumps(d, ensure_ascii=False, indent=2, default=str))
    resumo = os.getenv("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as f:
            f.write(f"## {titulo}\n\n```json\n{json.dumps(d, ensure_ascii=False, indent=2, default=str)}\n```\n")


def main(argv: list[str]) -> int:
    modo = argv[0] if argv else "listar"
    url = os.getenv("DATABASE_URL", "").strip()
    if not url.startswith(("postgresql://", "postgres://")):
        print("DATABASE_URL ausente ou fora do formato postgresql://", file=sys.stderr)
        return 2
    exigida = {"desativar": "DESATIVAR CONTAS DEMO", "reativar": "REATIVAR CONTAS DEMO"}.get(modo)
    if modo not in ("listar", "desativar", "reativar"):
        print("modo: listar | desativar | reativar", file=sys.stderr)
        return 2
    if exigida and os.getenv("CONFIRMACAO", "") != exigida:
        print(f"Recusado: para {modo}, CONFIRMACAO tem de ser exatamente \"{exigida}\"", file=sys.stderr)
        return 3
    c = Connection(url)
    try:
        if modo == "listar":
            c.execute_script("BEGIN TRANSACTION READ ONLY;")
            antes = listar(c)
            c.execute_script("ROLLBACK;")
            _imprime("Antes (somente leitura)", antes)
            print(f"::notice title=Contas de demonstração::{len(antes['contas_demo'])} contas demo "
                  f"({sum(1 for u in antes['contas_demo'] if u['status'] == 'active')} ativas) · {antes['contas_reais']} reais · "
                  f"{len(antes['orgs_so_demo'])} organizações só de demo · conteúdo público: {antes['conteudo_publico_das_orgs_demo']}")
            return 0
        c.execute_script("BEGIN;")
        try:
            feito = desativar(c) if modo == "desativar" else reativar(c)
            depois = listar(c)
            c.execute_script("COMMIT;")
        except Exception:
            c.execute_script("ROLLBACK;")
            raise
        _imprime(f"Resultado ({modo})", feito)
        _imprime("Depois", depois)
        ativas = sum(1 for u in depois["contas_demo"] if u["status"] == "active")
        print(f"::notice title=Contas de demonstração ({modo})::{feito} · contas demo ainda ativas: {ativas}")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
