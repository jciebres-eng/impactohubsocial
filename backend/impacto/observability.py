"""Logs estruturados (JSON), métricas no formato Prometheus e correlação por request_id.

Responde: o que quebrou (rota/status/erro), quando (ts), quem foi afetado (user_id/org_id), qual serviço
(service/version/env) e causa provável (error_type + error_id correlacionável com o stack trace no log).
Nunca registra senhas, tokens, corpo de requisição ou conteúdo de documentos.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import sys
import threading
import time
from collections import defaultdict
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
spans_var: ContextVar[list | None] = ContextVar("spans", default=None)
_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


def new_trace(traceparent: str | None) -> tuple[str, str]:
    """W3C Trace Context: aceita traceparent válido (propaga o trace_id) ou inicia um novo. Retorna (trace_id, span_id)."""
    m = _TRACEPARENT.match((traceparent or "").strip().lower())
    trace = m.group(1) if m and m.group(1) != "0" * 32 else secrets.token_hex(16)
    return trace, secrets.token_hex(8)


def add_span(name: str, started: float) -> None:
    """Registra um trecho medido (ex.: transação de banco) na lista do request atual — sem exportador externo."""
    spans = spans_var.get()
    if spans is not None and len(spans) < 200:
        spans.append((name, round((time.perf_counter() - started) * 1000, 2)))


def summarize_spans(spans: list | None) -> dict:
    agg: dict[str, list] = {}
    for n, ms in spans or []:
        a = agg.setdefault(n, [0, 0.0])
        a[0] += 1
        a[1] += ms
    return {n: {"count": c, "ms": round(t, 1)} for n, (c, t) in agg.items()}


_PII = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|\d{6,}|[A-Za-z0-9_-]{24,}")


def error_fingerprint(route: str, exc: BaseException) -> tuple[str, str]:
    """Impressão digital estável (rota + tipo + último frame do projeto) e mensagem sem e-mails/números longos/tokens."""
    tb = exc.__traceback__
    where = ""
    while tb is not None:
        fn = tb.tb_frame.f_code.co_filename
        if "impacto" in fn:
            where = f"{fn.rsplit('impacto', 1)[-1]}:{tb.tb_lineno}"
        tb = tb.tb_next
    fp = hashlib.sha256(f"{route}|{type(exc).__name__}|{where}".encode()).hexdigest()[:32]
    return fp, _PII.sub("[x]", str(exc))[:300]
_SERVICE = {"service": "impacto-api"}
_REDACT_KEYS = {"password", "token", "access_token", "refresh_token", "authorization", "secret", "code", "cookie", "api_key"}


def _redact(obj):
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if k.lower() in _REDACT_KEYS else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(), "logger": record.name, "msg": record.getMessage(),
            "request_id": request_id_var.get(), **_SERVICE,
        }
        if trace_id_var.get():
            base["trace_id"] = trace_id_var.get()
        extra = getattr(record, "fields", None)
        if extra:
            base.update(_redact(extra))
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO", version: str = "", env: str = "") -> None:
    _SERVICE.update({"version": version, "env": env})
    root = logging.getLogger()
    root.handlers.clear()
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.addHandler(h)
    root.setLevel(level.upper())
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).disabled = True


def log(logger: logging.Logger, level: int, msg: str, **fields) -> None:
    logger.log(level, msg, extra={"fields": fields})


# ------------------------------------------------------------------------------------------------
# Métricas (exposição texto Prometheus 0.0.4) — sem dependências externas
# ------------------------------------------------------------------------------------------------
_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)


class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.counters: dict[tuple, float] = defaultdict(float)
        self.hist: dict[tuple, list] = {}
        self.gauges: dict[tuple, float] = {}
        self.started = time.time()

    def inc(self, name: str, value: float = 1.0, **labels) -> None:
        with self._lock:
            self.counters[(name, tuple(sorted(labels.items())))] += value

    def observe(self, name: str, value: float, **labels) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            h = self.hist.setdefault(key, [[0] * len(_BUCKETS), 0.0, 0])
            for i, b in enumerate(_BUCKETS):
                if value <= b:
                    h[0][i] += 1
            h[1] += value
            h[2] += 1

    def set(self, name: str, value: float, **labels) -> None:
        with self._lock:
            self.gauges[(name, tuple(sorted(labels.items())))] = value

    @staticmethod
    def _lbl(labels, extra=()):
        items = list(labels) + list(extra)
        if not items:
            return ""
        return "{" + ",".join(f'{k}="{str(v).replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"' for k, v in items) + "}"

    def render(self) -> str:
        out = [f"# TYPE impacto_uptime_seconds gauge", f"impacto_uptime_seconds {time.time() - self.started:.0f}"]
        with self._lock:
            names = sorted({k[0] for k in self.counters})
            for n in names:
                out.append(f"# TYPE {n} counter")
                for (name, labels), v in sorted(self.counters.items()):
                    if name == n:
                        out.append(f"{n}{self._lbl(labels)} {v:g}")
            for n in sorted({k[0] for k in self.gauges}):
                out.append(f"# TYPE {n} gauge")
                for (name, labels), v in sorted(self.gauges.items()):
                    if name == n:
                        out.append(f"{n}{self._lbl(labels)} {v:g}")
            for n in sorted({k[0] for k in self.hist}):
                out.append(f"# TYPE {n} histogram")
                for (name, labels), (buckets, total, count) in sorted(self.hist.items()):
                    if name != n:
                        continue
                    for b, c in zip(_BUCKETS, buckets):
                        out.append(f"{n}_bucket{self._lbl(labels, [('le', b)])} {c}")
                    out.append(f"{n}_bucket{self._lbl(labels, [('le', '+Inf')])} {count}")
                    out.append(f"{n}_sum{self._lbl(labels)} {total:.6f}")
                    out.append(f"{n}_count{self._lbl(labels)} {count}")
        return "\n".join(out) + "\n"


METRICS = Metrics()
