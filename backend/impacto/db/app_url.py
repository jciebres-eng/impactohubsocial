"""Troca o usuário de uma URL administrativa pelo papel da aplicação (`impacto_app`).

O contêiner migra com a conexão ADMINISTRATIVA e depois serve com `impacto_app`. A troca era um
Python embutido no shell e não sabia do pooler do Supabase: pelo Supavisor (o único caminho IPv4 até
um projeto Supabase — a conexão direta `db.<ref>.supabase.co` é IPv6, e o GitHub Actions não tem
IPv6) o usuário vem como `postgres.<ref-do-projeto>`, e o papel da aplicação tem de ir como
`impacto_app.<ref-do-projeto>`, ou o pooler não sabe a que projeto encaminhar.

Uso: python3 -m impacto.db.app_url   (lê DATABASE_URL e IMPACTO_APP_PASSWORD; imprime a URL nova)
"""
from __future__ import annotations

import os
import sys
from urllib.parse import quote, unquote, urlsplit, urlunsplit

PAPEL = "impacto_app"


def app_dsn(admin_url: str, senha: str) -> str:
    u = urlsplit(admin_url)
    if u.scheme not in ("postgres", "postgresql") or not u.netloc or "@" not in u.netloc:
        raise ValueError("DATABASE_URL precisa ser uma URI postgresql://usuario:senha@host/banco")
    credencial, host = u.netloc.rsplit("@", 1)
    usuario = unquote(credencial.split(":", 1)[0])
    # `postgres.abcdefghijkl` → sufixo de projeto do pooler; `postgres` sozinho → conexão direta.
    sufixo = "." + usuario.split(".", 1)[1] if "." in usuario else ""
    netloc = f"{quote(PAPEL + sufixo, safe='.')}:{quote(senha, safe='')}@{host}"
    return urlunsplit((u.scheme, netloc, u.path, u.query, u.fragment))


def main() -> int:
    try:
        print(app_dsn(os.environ["DATABASE_URL"], os.environ["IMPACTO_APP_PASSWORD"]))
    except (KeyError, ValueError) as exc:
        print(f"app_url: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
