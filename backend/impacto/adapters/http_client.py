"""Cliente HTTP mínimo (urllib) com timeout, retries exponenciais e injeção para testes."""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

Transport = Callable[[str, str, dict, bytes | None, float], tuple[int, dict, bytes]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirecionamentos não são seguidos (evita SSRF por redirecionamento para rede interna)."""

    def redirect_request(self, *a, **kw):  # noqa: D401
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def check_destination(url: str) -> None:
    """Bloqueia destinos internos (SSRF): só https; IPs privados, link-local (metadados de nuvem), reservados e
    multicast são recusados. Loopback http só em development/test. Limitação: resolução DNS e conexão são passos
    separados (risco residual de DNS rebinding — mitigar também na camada de rede/egress da infraestrutura)."""
    u = urllib.parse.urlsplit(url)
    host = u.hostname or ""
    dev = os.getenv("IMPACTO_ENV", "development") in ("development", "test")
    if u.scheme != "https" and not (dev and u.scheme == "http" and host in ("127.0.0.1", "localhost")):
        raise ValueError("Somente HTTPS é permitido para provedores externos")
    if not host:
        raise ValueError("URL sem host")
    try:
        infos = socket.getaddrinfo(host, u.port or (443 if u.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise OSError(f"DNS: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_loopback and dev:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValueError("Destino de rede interna não permitido")


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None, timeout: float) -> tuple[int, dict, bytes]:
    check_destination(url)
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with _OPENER.open(req, timeout=timeout) as r:  # noqa: S310
            return r.status, dict(r.headers), r.read(10_000_000)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read(1_000_000)


class HttpClient:
    def __init__(self, transport: Transport = urllib_transport, retries: int = 2, backoff: float = 0.5):
        self.transport, self.retries, self.backoff = transport, retries, backoff

    def request(self, method: str, url: str, *, headers: dict | None = None, json_body=None, data: bytes | None = None,
                timeout: float = 20.0) -> tuple[int, dict, bytes]:
        h = dict(headers or {})
        body = data
        if json_body is not None:
            body = json.dumps(json_body).encode()
            h.setdefault("Content-Type", "application/json")
        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                status, rh, raw = self.transport(method, url, h, body, timeout)
                if status in (429, 500, 502, 503, 504) and attempt < self.retries:
                    time.sleep(self.backoff * (2 ** attempt))
                    continue
                return status, rh, raw
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(self.backoff * (2 ** attempt))
        raise RuntimeError(f"Falha de rede após {self.retries + 1} tentativas: {type(last_exc).__name__}")
