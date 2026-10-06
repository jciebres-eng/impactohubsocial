"""Registro de execução de tarefa operacional."""
from __future__ import annotations

import time
from contextlib import contextmanager

from ..db.pq import Connection


@contextmanager
def record(conn: Connection, job: str):
    """Abre uma execução, fecha com o resultado — mesmo quando a tarefa estoura.

    Uso:
        with record(c, "backup") as r:
            ...
            r["status"], r["detail"] = "ok", {...}

    Se o corpo levantar, a execução é fechada como `failed` com a primeira linha do erro e a exceção
    continua subindo: engolir a exceção aqui transformaria falha em silêncio, que é o defeito que
    este módulo existe para corrigir.
    """
    inicio = time.monotonic()
    row = conn.one("INSERT INTO ops_job_runs(job, status) VALUES ($1,'skipped') RETURNING id", job)
    estado: dict = {"status": "skipped", "detail": {}, "error": None}
    try:
        yield estado
    except Exception as exc:
        estado["status"] = "failed"
        estado["error"] = f"{type(exc).__name__}: {exc}".split("\n")[0][:2000]
        _fechar(conn, row["id"], estado, inicio)
        raise
    _fechar(conn, row["id"], estado, inicio)


def _fechar(conn: Connection, run_id: int, estado: dict, inicio: float) -> None:
    from ..db.pq import Json
    conn.run("UPDATE ops_job_runs SET status = $2, finished_at = now(), duration_ms = $3,"
             " detail = $4::jsonb, error = $5 WHERE id = $1",
             run_id, estado["status"], int((time.monotonic() - inicio) * 1000),
             Json(estado["detail"] or {}), estado["error"])


def last(conn: Connection, job: str) -> dict | None:
    return conn.one("SELECT id, job, status, started_at, finished_at, duration_ms, detail, error"
                    " FROM ops_job_runs WHERE job = $1 ORDER BY started_at DESC LIMIT 1", job)


def due(conn: Connection, job: str, *, every_seconds: int) -> bool:
    """A tarefa está na hora? Conta do ÚLTIMO SUCESSO, não da última tentativa.

    Contar da última tentativa faria uma falha repetida parecer "já rodou": o backup falharia às 3h,
    a próxima janela só abriria no dia seguinte e ninguém teria backup por 24 horas.
    """
    ultimo = conn.scalar("SELECT started_at FROM ops_job_runs WHERE job = $1 AND status = 'ok'"
                         " ORDER BY started_at DESC LIMIT 1", job)
    if ultimo is None:
        return True
    return bool(conn.scalar("SELECT $1::timestamptz < now() - make_interval(secs => $2::int)",
                            ultimo, every_seconds))
