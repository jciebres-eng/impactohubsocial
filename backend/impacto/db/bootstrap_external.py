"""Cria o papel `impacto_app` num PostgreSQL gerenciado, onde `infra/db/bootstrap.sql` não pode rodar.

O Supabase entrega o banco `postgres` pronto, com o usuário administrativo do projeto; não cria os
papéis da aplicação. Este comando é idempotente, roda com a conexão administrativa (`DATABASE_URL`)
ANTES das migrações, e recebe a senha do papel só por `IMPACTO_APP_PASSWORD`.

A versão recebida de fora, sem `IMPACTO_APP_PASSWORD`, usava a senha da própria conexão
administrativa para o papel da aplicação. Isso faz a aplicação carregar a credencial do
administrador — exatamente o que o papel separado existe para impedir. Aqui a variável é obrigatória
e nada é derivado da URL.

Num banco gerenciado o dono do schema é o usuário administrativo do projeto (não existe
`impacto_owner`); as migrações rodam como ele, e `impacto_app` recebe os GRANTs pelas migrações.
"""
from __future__ import annotations

import os

from .pq import Connection


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def ensure_app_role(conn: Connection, password: str) -> bool:
    """Cria `impacto_app` se não existir. Devolve True se criou. Nunca altera senha de papel existente."""
    if conn.scalar("SELECT 1 FROM pg_roles WHERE rolname = 'impacto_app'"):
        return False
    conn.execute_script(
        "CREATE ROLE impacto_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT PASSWORD "
        + _literal(password))
    return True


def main() -> int:
    dsn = os.getenv("DATABASE_URL", "")
    senha = os.getenv("IMPACTO_APP_PASSWORD", "")
    if not dsn:
        raise SystemExit("DATABASE_URL ausente")
    if len(senha) < 16:
        raise SystemExit("IMPACTO_APP_PASSWORD ausente ou curta (<16): a senha do papel da aplicação não é derivada de nada")
    conn = Connection(dsn)
    try:
        criado = ensure_app_role(conn, senha)
    finally:
        conn.close()
    print("papel impacto_app criado" if criado else "papel impacto_app já existia (senha não alterada)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
