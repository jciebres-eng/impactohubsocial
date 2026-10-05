"""Rate limiting persistido no PostgreSQL (funciona com várias instâncias da API).

Janela deslizante simples por (bucket, chave). Limpeza periódica em jobs.maintenance().
Para tráfego muito alto, recomenda-se adicionalmente limitação na borda (CDN/WAF/ingress).
"""
from __future__ import annotations

import os

from ..db.pool import DbContext
from ..http import ApiError


def _multiplier() -> int:
    """RATE_LIMIT_MULTIPLIER > 1 só é aceito em development/test (config.validate bloqueia em staging/production)."""
    try:
        return max(1, int(os.getenv("RATE_LIMIT_MULTIPLIER", "1")))
    except ValueError:
        return 1


def count(pool, bucket: str, key: str, window_seconds: int) -> int:
    with pool.tx(DbContext(system=True)) as c:
        return c.scalar("SELECT count(*) FROM rate_events WHERE bucket=$1 AND key=$2 AND at > now() - make_interval(secs => $3)",
                        bucket, key, window_seconds)


def record(pool, bucket: str, key: str) -> None:
    with pool.tx(DbContext(system=True)) as c:
        c.run("INSERT INTO rate_events(bucket, key) VALUES ($1,$2)", bucket, key)


def hit(ctx, bucket: str, key: str, limit: int, window_seconds: int) -> None:
    """Registra uma tentativa e levanta 429 se o limite foi excedido."""
    limit = limit * _multiplier()
    with ctx.pool.tx(DbContext(system=True)) as c:
        c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", (bucket + ":" + key,))
        n = c.scalar("SELECT count(*) FROM rate_events WHERE bucket=$1 AND key=$2 AND at > now() - make_interval(secs => $3)",
                     bucket, key, window_seconds)
        if n >= limit:
            raise ApiError(429, "rate_limited", "Muitas tentativas. Aguarde alguns minutos e tente novamente.")
        c.run("INSERT INTO rate_events(bucket, key) VALUES ($1,$2)", bucket, key)
