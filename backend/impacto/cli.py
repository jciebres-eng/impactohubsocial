"""Comandos operacionais.

python -m impacto.cli create-admin --email ops@empresa.com --name "Fulano"   # senha lida do stdin (nunca por argumento)
python -m impacto.cli seed-demo                                              # SOMENTE development/test
python -m impacto.cli gen-secrets                                            # gera valores para SECRET_KEY etc. (não grava nada)
"""
from __future__ import annotations

import argparse
import getpass
import secrets
import sys

from .security.crypto import generate_key


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="impacto")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("create-admin")
    a.add_argument("--email", required=True)
    a.add_argument("--name", required=True)
    sub.add_parser("seed-demo")
    sub.add_parser("gen-secrets")
    args = p.parse_args(argv)

    if args.cmd == "gen-secrets":
        print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
        print(f"VOUCHER_HMAC_KEY={secrets.token_urlsafe(48)}")
        print(f"FIELD_ENCRYPTION_KEY={generate_key()}")
        print(f"METRICS_TOKEN={secrets.token_urlsafe(32)}")
        return 0

    from .app import AppState
    from .config import load_settings
    from .db.pool import DbContext
    from .security import passwords
    state = AppState(load_settings())

    if args.cmd == "seed-demo":
        if state.settings.env not in ("development", "test"):
            print("Recusado: seed de demonstração só em development/test", file=sys.stderr)
            return 1
        from .seed_dev import seed
        print(seed(state, force=True))
        return 0

    if args.cmd == "create-admin":
        pw = sys.stdin.readline().rstrip("\n") if not sys.stdin.isatty() else getpass.getpass("Senha do administrador: ")
        probs = passwords.password_problems(pw, args.email)
        if probs or len(pw) < 14:
            print("Senha fraca (mínimo 14 caracteres para administradores): " + "; ".join(probs), file=sys.stderr)
            return 1
        with state.pool.tx(DbContext(system=True)) as c:
            org = c.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1")
            if not org:
                org = c.scalar("INSERT INTO organizations(kind, legal_name, compliance_status) VALUES ('platform','Administração da Plataforma','approved')"
                               " RETURNING id::text")
            uid = c.scalar("INSERT INTO users(email, full_name, password_hash, is_platform_admin, email_verified_at) VALUES ($1,$2,$3,true, now())"
                           " ON CONFLICT (email) DO UPDATE SET is_platform_admin = true RETURNING id::text",
                           args.email.lower(), args.name, passwords.hash_password(pw))
            c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'owner') ON CONFLICT DO NOTHING", uid, org)
            c.run("INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, payload) VALUES ($1,$2,'admin.created','user',$2,'{}')",
                  org, uid)
        print(f"Administrador criado: {args.email}. No primeiro login, ative o MFA (obrigatório para a área administrativa).")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
