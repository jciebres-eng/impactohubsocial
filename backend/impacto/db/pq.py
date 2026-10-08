"""Driver PostgreSQL mínimo sobre libpq (biblioteca cliente oficial do PostgreSQL) via ctypes.

Por que existe (ADR-016): o ambiente de build não tinha acesso a PyPI, então psycopg não pôde ser
instalado. libpq é a mesma biblioteca que o psycopg usa internamente. Este módulo:

* usa SEMPRE ``PQexecParams`` com parâmetros separados do SQL (sem interpolação → sem SQL injection);
* converte tipos com base no OID retornado pelo servidor;
* mapeia SQLSTATE para exceções tipadas;
* é thread-safe por conexão (cada conexão é usada por uma thread por vez, garantido pelo pool).

A interface pública (``Connection.execute/query/one/scalar``) é pequena de propósito, para que a troca
por psycopg 3 seja um adapter de ~80 linhas (ver docs/DATABASE.md).
"""
from __future__ import annotations

import ctypes
import ctypes.util
import json
import uuid
from datetime import date, datetime, time, UTC
from decimal import Decimal
from typing import Any
from collections.abc import Iterable, Sequence

# --------------------------------------------------------------------------------------------
# Carregamento da libpq
# --------------------------------------------------------------------------------------------
_libname = ctypes.util.find_library("pq") or "libpq.so.5"
try:
    _lib = ctypes.CDLL(_libname)
except OSError as exc:  # pragma: no cover - depende do SO
    raise ImportError(
        "libpq não encontrada. Instale o pacote do sistema 'libpq5' (Debian/Ubuntu) ou equivalente."
    ) from exc

_c = ctypes.c_char_p
_vp = ctypes.c_void_p
_lib.PQconnectdb.argtypes = [_c]
_lib.PQconnectdb.restype = _vp
_lib.PQstatus.argtypes = [_vp]
_lib.PQstatus.restype = ctypes.c_int
_lib.PQerrorMessage.argtypes = [_vp]
_lib.PQerrorMessage.restype = _c
_lib.PQfinish.argtypes = [_vp]
_lib.PQfinish.restype = None
_lib.PQreset.argtypes = [_vp]
_lib.PQreset.restype = None
_lib.PQexec.argtypes = [_vp, _c]
_lib.PQexec.restype = _vp
_lib.PQexecParams.argtypes = [
    _vp, _c, ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(_c),
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.c_int,
]
_lib.PQexecParams.restype = _vp
_lib.PQresultStatus.argtypes = [_vp]
_lib.PQresultStatus.restype = ctypes.c_int
_lib.PQresultErrorField.argtypes = [_vp, ctypes.c_int]
_lib.PQresultErrorField.restype = _c
_lib.PQresultErrorMessage.argtypes = [_vp]
_lib.PQresultErrorMessage.restype = _c
_lib.PQntuples.argtypes = [_vp]
_lib.PQntuples.restype = ctypes.c_int
_lib.PQnfields.argtypes = [_vp]
_lib.PQnfields.restype = ctypes.c_int
_lib.PQfname.argtypes = [_vp, ctypes.c_int]
_lib.PQfname.restype = _c
_lib.PQftype.argtypes = [_vp, ctypes.c_int]
_lib.PQftype.restype = ctypes.c_uint
_lib.PQgetvalue.argtypes = [_vp, ctypes.c_int, ctypes.c_int]
_lib.PQgetvalue.restype = ctypes.POINTER(ctypes.c_char)
_lib.PQgetlength.argtypes = [_vp, ctypes.c_int, ctypes.c_int]
_lib.PQgetlength.restype = ctypes.c_int
_lib.PQgetisnull.argtypes = [_vp, ctypes.c_int, ctypes.c_int]
_lib.PQgetisnull.restype = ctypes.c_int
_lib.PQcmdTuples.argtypes = [_vp]
_lib.PQcmdTuples.restype = _c
_lib.PQclear.argtypes = [_vp]
_lib.PQclear.restype = None
_lib.PQtransactionStatus.argtypes = [_vp]
_lib.PQtransactionStatus.restype = ctypes.c_int
_lib.PQserverVersion.argtypes = [_vp]
_lib.PQserverVersion.restype = ctypes.c_int

CONNECTION_OK = 0
PGRES_EMPTY_QUERY, PGRES_COMMAND_OK, PGRES_TUPLES_OK = 0, 1, 2
PQTRANS_IDLE, PQTRANS_ACTIVE, PQTRANS_INTRANS, PQTRANS_INERROR, PQTRANS_UNKNOWN = 0, 1, 2, 3, 4
_DIAG_SQLSTATE, _DIAG_MESSAGE, _DIAG_DETAIL, _DIAG_CONSTRAINT = ord("C"), ord("M"), ord("D"), ord("n")


# --------------------------------------------------------------------------------------------
# Exceções (hierarquia inspirada em DB-API 2.0)
# --------------------------------------------------------------------------------------------
class DatabaseError(Exception):
    sqlstate: str | None = None

    def __init__(self, message: str, sqlstate: str | None = None, constraint: str | None = None,
                 detail: str | None = None):
        super().__init__(message)
        self.sqlstate = sqlstate
        self.constraint = constraint
        self.detail = detail


class OperationalError(DatabaseError):
    """Falha de conexão/infra."""


class IntegrityError(DatabaseError):
    pass


class UniqueViolation(IntegrityError):
    pass


class ForeignKeyViolation(IntegrityError):
    pass


class CheckViolation(IntegrityError):
    pass


class NotNullViolation(IntegrityError):
    pass


class InsufficientPrivilege(DatabaseError):
    """Inclui violação de política RLS (SQLSTATE 42501)."""


class SerializationFailure(DatabaseError):
    pass


class QueryCanceled(DatabaseError):
    pass


class RaiseException(DatabaseError):
    """Erro levantado por trigger/função (P0001)."""


_SQLSTATE_MAP: dict[str, type[DatabaseError]] = {
    "23505": UniqueViolation,
    "23503": ForeignKeyViolation,
    "23514": CheckViolation,
    "23502": NotNullViolation,
    "42501": InsufficientPrivilege,
    "40001": SerializationFailure,
    "40P01": SerializationFailure,
    "57014": QueryCanceled,
    "P0001": RaiseException,
}


def _error_for(sqlstate: str | None) -> type[DatabaseError]:
    if not sqlstate:
        return DatabaseError
    if sqlstate in _SQLSTATE_MAP:
        return _SQLSTATE_MAP[sqlstate]
    if sqlstate.startswith("23"):
        return IntegrityError
    if sqlstate.startswith("08"):
        return OperationalError
    return DatabaseError


# --------------------------------------------------------------------------------------------
# Conversão de tipos
# --------------------------------------------------------------------------------------------
class Json:
    """Marca explicitamente um valor como JSON (útil para listas que devem virar jsonb, não array)."""

    __slots__ = ("value",)

    def __init__(self, value: Any):
        self.value = value


def _array_literal(items: Iterable[Any]) -> str:
    out = []
    for it in items:
        if it is None:
            out.append("NULL")
            continue
        s = _to_text(it)
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        out.append(f'"{s}"')
    return "{" + ",".join(out) + "}"


def _to_text(v: Any) -> str:
    if isinstance(v, bool):
        return "t" if v else "f"
    if isinstance(v, (int, float, Decimal)):
        return str(v)
    if isinstance(v, str):
        return v
    if isinstance(v, datetime):
        if v.tzinfo is None:
            raise ValueError("datetime sem timezone não é aceito; use UTC explícito")
        return v.isoformat()
    if isinstance(v, (date, time)):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, Json):
        return json.dumps(v.value, ensure_ascii=False, separators=(",", ":"), default=str)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"), default=str)
    if isinstance(v, (list, tuple, set, frozenset)):
        return _array_literal(sorted(v) if isinstance(v, (set, frozenset)) else v)
    if isinstance(v, bytes):
        return "\\x" + v.hex()
    raise TypeError(f"Tipo de parâmetro não suportado: {type(v).__name__}")


def _parse_array(text: str, elem: callable) -> list:
    # Arrays 1-D no formato texto do PostgreSQL: {a,"b c",NULL}
    if text == "{}":
        return []
    assert text[0] == "{" and text[-1] == "}", text
    body = text[1:-1]
    items: list = []
    i, n = 0, len(body)
    while i < n:
        if body[i] == '"':
            i += 1
            buf = []
            while body[i] != '"':
                if body[i] == "\\":
                    i += 1
                buf.append(body[i])
                i += 1
            i += 1  # aspas de fechamento
            items.append(elem("".join(buf)))
        else:
            j = body.find(",", i)
            j = n if j == -1 else j
            tok = body[i:j]
            items.append(None if tok == "NULL" else elem(tok))
            i = j
        if i < n and body[i] == ",":
            i += 1
    return items


def _parse_bool(s: str) -> bool:
    return s == "t"


def _parse_ts(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _parse_json(s: str) -> Any:
    return json.loads(s)


def _parse_bytea(s: str) -> bytes:
    return bytes.fromhex(s[2:]) if s.startswith("\\x") else s.encode()


_SCALAR: dict[int, callable] = {
    16: _parse_bool, 17: _parse_bytea, 20: int, 21: int, 23: int, 26: int,
    700: float, 701: float, 1700: Decimal,
    114: _parse_json, 3802: _parse_json,
    1082: date.fromisoformat, 1114: _parse_ts, 1184: _parse_ts,
    2950: str,
}
_ARRAY: dict[int, callable] = {
    1000: _parse_bool, 1005: int, 1007: int, 1016: int, 1009: str, 1015: str, 2951: str,
    1022: float, 1231: Decimal, 3807: _parse_json, 1182: date.fromisoformat, 1185: _parse_ts,
}


def _convert(oid: int, raw: str) -> Any:
    f = _SCALAR.get(oid)
    if f is not None:
        return f(raw)
    e = _ARRAY.get(oid)
    if e is not None:
        return _parse_array(raw, e)
    return raw


# --------------------------------------------------------------------------------------------
# Conexão
# --------------------------------------------------------------------------------------------
class Result:
    __slots__ = ("rows", "rowcount")

    def __init__(self, rows: list[dict], rowcount: int):
        self.rows = rows
        self.rowcount = rowcount


class Connection:
    def __init__(self, dsn: str):
        self._conn = _lib.PQconnectdb(dsn.encode())
        if not self._conn or _lib.PQstatus(self._conn) != CONNECTION_OK:
            msg = _lib.PQerrorMessage(self._conn).decode(errors="replace") if self._conn else "sem memória"
            if self._conn:
                _lib.PQfinish(self._conn)
            self._conn = None
            raise OperationalError(f"Falha ao conectar no PostgreSQL: {msg.strip()}")
        # Banco gerenciado (Supabase) instala pgcrypto na schema `extensions`. As funções do produto
        # que chamam digest() fixam o próprio search_path (migração 0063); isto aqui cobre o que roda
        # FORA delas na mesma sessão — SQL de migração com digest() inline, consulta ad hoc. Só entra
        # na lista se a schema existir: `public` continua primeiro, e num PostgreSQL comum a sessão
        # fica exatamente como era. A versão recebida de fora fazia o SET incondicional.
        self.execute("SELECT set_config('search_path', CASE WHEN EXISTS (SELECT 1 FROM pg_namespace"
                     " WHERE nspname = 'extensions') THEN 'public, extensions' ELSE 'public' END, false)")

    # -- ciclo de vida -------------------------------------------------------------------------
    @property
    def closed(self) -> bool:
        return self._conn is None

    def healthy(self) -> bool:
        return self._conn is not None and _lib.PQstatus(self._conn) == CONNECTION_OK

    def reset(self) -> None:
        if self._conn:
            _lib.PQreset(self._conn)

    def close(self) -> None:
        if self._conn:
            _lib.PQfinish(self._conn)
            self._conn = None

    def transaction_status(self) -> int:
        return _lib.PQtransactionStatus(self._conn) if self._conn else PQTRANS_UNKNOWN


    def __del__(self):  # pragma: no cover
        try:
            self.close()
        except Exception:  # noqa: S110 - destrutor: fechar é best-effort
            pass

    # -- execução ------------------------------------------------------------------------------
    def _check(self, res) -> None:
        if not res:
            raise OperationalError(_lib.PQerrorMessage(self._conn).decode(errors="replace").strip())
        st = _lib.PQresultStatus(res)
        if st in (PGRES_EMPTY_QUERY, PGRES_COMMAND_OK, PGRES_TUPLES_OK):
            return
        def field(code):
            v = _lib.PQresultErrorField(res, code)
            return v.decode(errors="replace") if v else None
        sqlstate = field(_DIAG_SQLSTATE)
        message = field(_DIAG_MESSAGE) or _lib.PQresultErrorMessage(res).decode(errors="replace").strip()
        exc_t = _error_for(sqlstate)
        detail, constraint = field(_DIAG_DETAIL), field(_DIAG_CONSTRAINT)
        _lib.PQclear(res)
        raise exc_t(message, sqlstate=sqlstate, constraint=constraint, detail=detail)

    def execute_script(self, sql: str) -> None:
        """Executa SQL multi-statement SEM parâmetros (uso exclusivo do runner de migrations)."""
        res = _lib.PQexec(self._conn, sql.encode())
        self._check(res)
        _lib.PQclear(res)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Result:
        if self._conn is None:
            raise OperationalError("Conexão fechada")
        n = len(params)
        values = (_c * n)()
        for i, p in enumerate(params):
            values[i] = None if p is None else _to_text(p).encode()
        res = _lib.PQexecParams(self._conn, sql.encode(), n, None, values if n else None, None, None, 0)
        self._check(res)
        try:
            nt, nf = _lib.PQntuples(res), _lib.PQnfields(res)
            names = [_lib.PQfname(res, j).decode() for j in range(nf)]
            types = [_lib.PQftype(res, j) for j in range(nf)]
            rows: list[dict] = []
            for i in range(nt):
                row = {}
                for j in range(nf):
                    if _lib.PQgetisnull(res, i, j):
                        row[names[j]] = None
                    else:
                        ln = _lib.PQgetlength(res, i, j)
                        raw = ctypes.string_at(_lib.PQgetvalue(res, i, j), ln).decode()
                        row[names[j]] = _convert(types[j], raw)
                rows.append(row)
            ct = _lib.PQcmdTuples(res)
            rowcount = int(ct) if ct else nt
            return Result(rows, rowcount)
        finally:
            _lib.PQclear(res)

    # Atalhos
    def query(self, sql: str, *params: Any) -> list[dict]:
        return self.execute(sql, params).rows

    def one(self, sql: str, *params: Any) -> dict | None:
        rows = self.execute(sql, params).rows
        return rows[0] if rows else None

    def scalar(self, sql: str, *params: Any) -> Any:
        row = self.one(sql, *params)
        return next(iter(row.values())) if row else None

    def run(self, sql: str, *params: Any) -> int:
        return self.execute(sql, params).rowcount
