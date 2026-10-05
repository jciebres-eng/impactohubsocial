"""Transporte resiliente para sistemas externos.

REUTILIZA `adapters/http_client.HttpClient` (que já traz: só HTTPS, bloqueio de IP interno/metadados — guarda de SSRF —,
sem seguir redirecionamento, retries em 429/5xx). Acrescenta o que faltava: classificação temporário × permanente,
jitter, disjuntor por conexão, propagação de correlação e teto de tempo por chamada.
"""
from __future__ import annotations

import logging
import random
import time
from datetime import UTC, datetime, timedelta

from ..adapters.http_client import HttpClient
from ..observability import log
from .contracts import IntegrationError

logger = logging.getLogger("impacto.integrations")

RETRY_STATUS = (408, 425, 429, 500, 502, 503, 504)
CIRCUIT_THRESHOLD = 5          # falhas consecutivas antes de abrir o disjuntor
CIRCUIT_COOLDOWN_S = 300       # tempo de espera com o disjuntor aberto


def classify(status: int) -> str:
    """Erro temporário (pode repetir) × permanente (não repetir indefinidamente)."""
    if status in RETRY_STATUS:
        return "temporary"
    if 400 <= status < 500:
        return "permanent"
    return "temporary" if status >= 500 else "permanent"


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 30.0) -> float:
    """Espera exponencial com jitter (evita rajada sincronizada de reenvios)."""
    return min(cap, base * (2 ** attempt)) * (0.5 + random.random() / 2)  # noqa: S311 - jitter, não é uso criptográfico


class ResilientCaller:
    """Chamada externa com teto de tempo, tentativas, jitter e disjuntor. Nunca bloqueia indefinidamente o núcleo."""

    def __init__(self, connection: dict, *, http: HttpClient | None = None, correlation_id: str = "-",
                 timeout: float = 20.0, attempts: int = 3, sleep=time.sleep):
        self.connection = connection
        self.http = http or HttpClient(retries=0)      # as tentativas são controladas aqui (com jitter e classificação)
        self.correlation_id = correlation_id
        self.timeout = timeout
        self.attempts = max(1, attempts)
        self._sleep = sleep
        self.calls: list[dict] = []                    # trilha da chamada (sem corpo e sem segredo)

    # -------------------------------------------------------------------------------------- disjuntor
    def circuit_open(self, now: datetime | None = None) -> bool:
        until = self.connection.get("circuit_open_until")
        if not until:
            return False
        now = now or datetime.now(UTC)
        return bool(until > now)

    @staticmethod
    def next_circuit_state(failure_streak: int, *, temporary: bool) -> tuple[int, datetime | None]:
        """Novo (sequência de falhas, abertura do disjuntor). Erro permanente não abre o disjuntor: o problema é o pedido."""
        if not temporary:
            return failure_streak, None
        streak = failure_streak + 1
        if streak >= CIRCUIT_THRESHOLD:
            return streak, datetime.now(UTC) + timedelta(seconds=CIRCUIT_COOLDOWN_S)
        return streak, None

    # -------------------------------------------------------------------------------------- chamada
    def call(self, method: str, url: str, *, headers: dict | None = None, json_body=None, data: bytes | None = None,
             expected: tuple[int, ...] = (200, 201, 202, 204)) -> tuple[int, dict, bytes]:
        if self.circuit_open():
            raise IntegrationError("circuit_open", "Integração suspensa temporariamente após falhas consecutivas", kind="temporary")
        h = dict(headers or {})
        h.setdefault("X-Correlation-Id", self.correlation_id)
        h.setdefault("User-Agent", "ImpactoIntegrationHub/1.0")
        last: IntegrationError | None = None
        for attempt in range(self.attempts):
            started = time.perf_counter()
            try:
                status, rh, raw = self.http.request(method, url, headers=h, json_body=json_body, data=data, timeout=self.timeout)
            except ValueError as exc:                  # destino recusado pela guarda de SSRF: NUNCA repetir
                raise IntegrationError("destination_blocked", str(exc), kind="permanent") from exc
            except Exception as exc:                   # noqa: BLE001 - rede/timeout
                last = IntegrationError("network", f"Falha de rede: {type(exc).__name__}", kind="temporary")
                self._trace(method, url, None, started, attempt)
                if attempt + 1 < self.attempts:
                    self._sleep(backoff_delay(attempt))
                    continue
                raise last from exc
            self._trace(method, url, status, started, attempt)
            if status in expected:
                return status, rh, raw
            kind = classify(status)
            last = IntegrationError(f"http_{status}", f"Resposta inesperada do sistema externo (HTTP {status})",
                                    kind=kind, status=status, detail=raw[:300].decode("utf-8", "replace"))
            if kind == "permanent" or attempt + 1 >= self.attempts:
                raise last
            self._sleep(backoff_delay(attempt))
        raise last or IntegrationError("unknown", "Falha desconhecida", kind="temporary")

    def _trace(self, method: str, url: str, status: int | None, started: float, attempt: int) -> None:
        entry = {"method": method, "host": url.split("/")[2] if "://" in url else "?", "status": status,
                 "ms": round((time.perf_counter() - started) * 1000, 1), "attempt": attempt + 1}
        self.calls.append(entry)
        log(logger, logging.INFO, "integration_call", correlation_id=self.correlation_id,
            connection_id=str(self.connection.get("id")), **entry)


def assert_allowed_endpoint(url: str, *, allow_loopback: bool = False) -> None:
    """Valida a FORMA do endereço ao gravar a conexão: esquema e, quando o host é um IP literal, faixa permitida.

    NÃO resolve DNS aqui de propósito: a organização pode configurar um host que ainda não resolve (DNS interno, host a
    ser provisionado) e uma falha de DNS não deve impedir a configuração. A guarda de SSRF autoritativa roda na HORA DA
    CHAMADA (`check_destination` dentro do HttpClient), que resolve o nome e recusa rede interna/metadados.

    `allow_loopback` existe só para apontar uma CONEXÃO a um dublê local em desenvolvimento. Destino de webhook de
    saída (URL fornecida pelo cliente) nunca permite loopback nem rede privada, em nenhum ambiente.
    """
    import ipaddress
    import urllib.parse
    u = urllib.parse.urlsplit(url or "")
    host = u.hostname or ""
    dev = allow_loopback      # só quem chama decide: endpoint de ERP local em desenvolvimento, sim; webhook do cliente, nunca
    if not host:
        raise IntegrationError("endpoint_invalid", "Endereço sem host", kind="permanent")
    if u.scheme != "https" and not (dev and u.scheme == "http" and host in ("127.0.0.1", "localhost")):
        raise IntegrationError("destination_blocked", "Somente HTTPS é permitido para provedores externos", kind="permanent")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return                     # nome de domínio: a verificação real acontece na chamada
    if ip.is_loopback and dev:
        return
    if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
        raise IntegrationError("destination_blocked", "Destino de rede interna não permitido", kind="permanent")
