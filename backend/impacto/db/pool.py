"""Pool de conexões e transações com contexto de tenant (RLS).

Toda transação de request define, via ``set_config(..., is_local=true)``:

* ``app.user_id``         — usuário autenticado
* ``app.org_id``          — organização ativa (tenant)
* ``app.org_kind``        — osc | company | provider | platform
* ``app.platform_admin``  — 'on' somente para administradores da plataforma com MFA
* ``app.system``          — 'on' somente em caminhos de sistema auditados (auth, webhooks, jobs)

As políticas RLS (migrations/0002_rls.sql) usam essas variáveis. Como são LOCAL à transação,
não vazam entre requests que reutilizam a mesma conexão do pool.
"""
from __future__ import annotations

import contextlib
import queue
import threading
import time
from dataclasses import dataclass
from collections.abc import Iterator

from ..observability import add_span
from .pq import Connection, OperationalError, PQTRANS_IDLE


@dataclass(frozen=True)
class DbContext:
    user_id: str | None = None
    org_id: str | None = None
    org_kind: str | None = None
    platform_admin: bool = False
    system: bool = False

    @staticmethod
    def anonymous() -> DbContext:
        return DbContext()


class Pool:
    def __init__(self, dsn: str, max_size: int = 10, acquire_timeout: float = 10.0):
        self.dsn = dsn
        self.max_size = max_size
        self.acquire_timeout = acquire_timeout
        self._idle: queue.LifoQueue[Connection] = queue.LifoQueue()
        self._created = 0
        self._lock = threading.Lock()
        self._closed = False

    def _new(self) -> Connection:
        return Connection(self.dsn)

    def acquire(self) -> Connection:
        if self._closed:
            raise OperationalError("Pool fechado")
        try:
            conn = self._idle.get_nowait()
        except queue.Empty:
            with self._lock:
                can_create = self._created < self.max_size
                if can_create:
                    self._created += 1
            if can_create:
                try:
                    return self._new()
                except Exception:  # noqa: BLE001 - devolve a vaga contabilizada e RELANÇA
                    with self._lock:
                        self._created -= 1
                    raise
            try:
                conn = self._idle.get(timeout=self.acquire_timeout)
            except queue.Empty as exc:
                raise OperationalError("Tempo esgotado aguardando conexão do pool") from exc
        if not conn.healthy():
            conn.reset()
            if not conn.healthy():
                conn.close()
                with self._lock:
                    self._created -= 1
                return self.acquire()
        return conn

    def release(self, conn: Connection) -> None:
        if conn.closed:
            with self._lock:
                self._created -= 1
            return
        if conn.transaction_status() != PQTRANS_IDLE:
            try:
                conn.execute("ROLLBACK")
            except Exception:  # noqa: BLE001 - conexão que não aceita ROLLBACK é descartada, não devolvida ao pool
                conn.close()
                with self._lock:
                    self._created -= 1
                return
        if self._closed:
            conn.close()
            return
        self._idle.put(conn)

    def close(self) -> None:
        self._closed = True
        while True:
            try:
                self._idle.get_nowait().close()
            except queue.Empty:
                break

    @contextlib.contextmanager
    def connection(self) -> Iterator[Connection]:
        conn = self.acquire()
        try:
            yield conn
        finally:
            self.release(conn)

    @contextlib.contextmanager
    def tx(self, ctx: DbContext, *, readonly: bool = False, isolation: str | None = None) -> Iterator[Connection]:
        """Transação com contexto de segurança aplicado antes de qualquer query de negócio."""
        conn = self.acquire()
        _t0 = time.perf_counter()
        try:
            mode = []
            if isolation:
                assert isolation in ("SERIALIZABLE", "REPEATABLE READ", "READ COMMITTED")
                mode.append(f"ISOLATION LEVEL {isolation}")
            if readonly:
                mode.append("READ ONLY")
            conn.execute("BEGIN " + " ".join(mode))
            conn.execute(
                "SELECT set_config('app.user_id', $1, true), set_config('app.org_id', $2, true),"
                " set_config('app.org_kind', $3, true), set_config('app.platform_admin', $4, true),"
                " set_config('app.system', $5, true)",
                (ctx.user_id or "", ctx.org_id or "", ctx.org_kind or "",
                 "on" if ctx.platform_admin else "off", "on" if ctx.system else "off"),
            )
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            if not conn.closed:
                try:
                    conn.execute("ROLLBACK")
                except Exception:  # noqa: BLE001 - ROLLBACK de melhor esforço; a exceção original é RELANÇADA
                    conn.close()
            raise
        finally:
            add_span("db.tx", _t0)
            self.release(conn)



# NÃO existe aqui um `retry_serializable()`. Existiu, e nunca foi chamado: a estratégia desta
# plataforma para conflito de serialização é outra, e está em `http.py` — devolver 409
# `concurrent_update` e pedir que o cliente repita. Repetir no servidor esconderia do cliente que
# houve conflito, e em operação que envolve dinheiro ou decisão sobre terceiro isso é pior que o
# erro. A v0.20.0 removeu o utilitário morto para que ninguém o ligue achando que é o padrão.
