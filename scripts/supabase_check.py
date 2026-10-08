#!/usr/bin/env python3
"""Diagnóstico SOMENTE LEITURA de um PostgreSQL gerenciado (Supabase) antes de aplicar o IMPACTO.

Toda consulta roda em transação READ ONLY: o banco recusa qualquer escrita, então este script não
tem como alterar nada, mesmo com bug. Responde, antes de qualquer decisão irreversível:

  - quem é a conexão administrativa e o que ela pode (criar papel, conceder uso de `extensions`);
  - onde está o pgcrypto;
  - que migrações já estão aplicadas, quais faltam, quais mudaram e quais o repositório não conhece
    (a publicação de terceiro aplicou uma `0063_v0231_…` que não está aqui);
  - se `impacto_app` existe, se é seguro, e se a senha dele é a MESMA do administrador;
  - se o banco já tem dados (e quantas contas de demonstração).

Lê DATABASE_URL (administrativa) e, opcional, IMPACTO_APP_PASSWORD. Nunca imprime senha.
Em GitHub Actions, escreve o resultado também no resumo da execução e como anotações.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from impacto.db.app_url import app_dsn
from impacto.db.pq import Connection, DatabaseError

MIGRACOES = ROOT / "backend" / "migrations"
saida: list[str] = []
alertas: list[str] = []


def diz(texto: str) -> None:
    saida.append(texto)
    print(texto)


def alerta(texto: str) -> None:
    alertas.append(texto)
    diz(f"ATENÇÃO: {texto}")


def _tenta_login(url: str) -> str | None:
    try:
        c = Connection(url)
    except DatabaseError as exc:
        return None if "password authentication failed" in str(exc) else f"erro: {str(exc).splitlines()[0][:160]}"
    try:
        return c.scalar("SELECT current_user")
    finally:
        c.close()


def main() -> int:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL ausente", file=sys.stderr)
        return 2
    u = urlsplit(url)
    diz(f"## Diagnóstico do banco — somente leitura\n\nhost `{u.hostname}` · porta `{u.port or 5432}` · "
        f"usuário `{unquote(u.username or '')}`\n")
    if (u.hostname or "").startswith("db.") and (u.hostname or "").endswith(".supabase.co"):
        alerta("conexão DIRETA do Supabase (IPv6). GitHub Actions não tem IPv6: use a do pooler de sessão.")
    c = Connection(url)
    try:
        c.execute_script("BEGIN TRANSACTION READ ONLY;")
        diz(f"- servidor: {c.scalar('SHOW server_version')}")
        eu = c.one("SELECT current_user AS u, rolsuper, rolcreaterole FROM pg_roles WHERE rolname = current_user")
        diz(f"- conexão administrativa: `{eu['u']}` · superusuário={eu['rolsuper']} · cria papel={eu['rolcreaterole']}")
        if not eu["rolcreaterole"] and not eu["rolsuper"]:
            alerta("o administrador não pode criar papel: o bootstrap de impacto_app vai falhar")
        pg = c.scalar("SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace"
                      " WHERE e.extname = 'pgcrypto'")
        diz(f"- pgcrypto: {'schema `' + pg + '`' if pg else 'NÃO instalado'}")
        tem_ext = c.scalar("SELECT 1 FROM pg_namespace WHERE nspname = 'extensions'")
        if tem_ext:
            go = c.scalar("SELECT has_schema_privilege(current_user, 'extensions', 'USAGE WITH GRANT OPTION')")
            diz(f"- administrador pode conceder uso de `extensions`: {go}")
            if not go:
                alerta("sem GRANT OPTION em `extensions`: a migração 0063 não consegue dar uso a impacto_app")

        # ---- migrações
        repo = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(MIGRACOES.glob("[0-9][0-9][0-9][0-9]_*.sql"))}
        if c.scalar("SELECT to_regclass('public.schema_migrations') IS NOT NULL"):
            aplicadas = {r["version"]: r["checksum"] for r in c.query("SELECT version, checksum FROM schema_migrations")}
        else:
            aplicadas = {}
        pendentes = [v for v in repo if v not in aplicadas]
        mudadas = [v for v in repo if v in aplicadas and aplicadas[v] != repo[v]]
        estranhas = sorted(v for v in aplicadas if v not in repo)
        diz(f"- migrações: {len(aplicadas)} aplicadas · {len(pendentes)} pendentes · {len(mudadas)} com conteúdo diferente"
            f" · {len(estranhas)} que este repositório não conhece")
        for v in pendentes:
            diz(f"  - pendente: `{v}`")
        for v in estranhas:
            diz(f"  - aplicada e desconhecida aqui: `{v}`")
        if mudadas:
            alerta(f"migração aplicada com conteúdo diferente do repositório (o runner recusa): {mudadas}")

        # ---- papel da aplicação
        app = c.one("SELECT rolcanlogin, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'impacto_app'")
        if not app:
            diz("- `impacto_app`: não existe (o bootstrap cria)")
        else:
            diz(f"- `impacto_app`: login={app['rolcanlogin']} · superusuário={app['rolsuper']} · ignora RLS={app['rolbypassrls']}")
            if app["rolsuper"] or app["rolbypassrls"]:
                alerta("impacto_app é superusuário ou ignora RLS: o isolamento entre organizações não vale")
            if tem_ext:
                uso = c.scalar("SELECT has_schema_privilege('impacto_app', 'extensions', 'USAGE')")
                diz(f"- `impacto_app` usa `extensions`: {uso}")

        # ---- dados
        if c.scalar("SELECT to_regclass('public.users') IS NOT NULL"):
            n = c.scalar("SELECT count(*) FROM users")
            demo = c.scalar("SELECT count(*) FROM users WHERE email::text LIKE '%@demo.impacto.local'")
            orgs = c.scalar("SELECT count(*) FROM organizations") if c.scalar("SELECT to_regclass('public.organizations') IS NOT NULL") else 0
            diz(f"- dados: {n} usuários ({demo} de demonstração) · {orgs} organizações")
            if n - demo > 0:
                alerta(f"há {n - demo} usuário(s) que NÃO são de demonstração — trate este banco como tendo dado real")
        else:
            diz("- dados: banco sem as tabelas do IMPACTO")
        c.execute_script("ROLLBACK;")
    finally:
        c.close()

    # ---- senhas do papel da aplicação (tentativas de login, sem escrita)
    if app:
        senha_admin = unquote(u.password or "")
        if senha_admin and _tenta_login(app_dsn(url, senha_admin)) == "impacto_app":
            alerta("impacto_app aceita a SENHA DO ADMINISTRADOR: a aplicação carrega a credencial administrativa."
                   " Rode o modo aplicar com rotação de senha.")
        nova = os.getenv("IMPACTO_APP_PASSWORD", "")
        if nova:
            r = _tenta_login(app_dsn(url, nova))
            diz(f"- login de impacto_app com IMPACTO_APP_PASSWORD: {'OK' if r == 'impacto_app' else (r or 'senha não confere')}")

    diz("\n**Veredito:** " + ("nenhum impedimento encontrado." if not alertas else f"{len(alertas)} ponto(s) de atenção acima."))
    resumo = os.getenv("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8") as f:
            f.write("\n".join(saida) + "\n")
        for a in alertas:
            print(f"::warning title=Supabase::{a}")
        print("::notice title=Diagnóstico Supabase::" + " | ".join(l.strip("- ") for l in saida if l.startswith("- "))[:3500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
