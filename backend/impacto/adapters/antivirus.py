"""Antivírus: cliente clamd (protocolo INSTREAM via TCP). Sem antivírus configurado, arquivos ficam em
``pending_scan`` e o download é bloqueado em staging/production (ALLOW_UNSCANNED_DOWNLOADS=false)."""
from __future__ import annotations

import socket
import struct


class NoAntivirus:
    name = "none"

    def scan(self, data: bytes) -> tuple[str, str]:
        return "pending_scan", "antivírus não configurado"


class ClamdAntivirus:
    name = "clamd"

    def __init__(self, host: str, port: int, timeout: float = 30.0):
        self.host, self.port, self.timeout = host, port, timeout

    def scan(self, data: bytes) -> tuple[str, str]:
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 65536):
                chunk = data[i:i + 65536]
                s.sendall(struct.pack(">I", len(chunk)) + chunk)
            s.sendall(struct.pack(">I", 0))
            resp = b""
            while not resp.endswith(b"\0"):
                part = s.recv(4096)
                if not part:
                    break
                resp += part
        text = resp.rstrip(b"\0").decode(errors="replace")
        if text.endswith("OK"):
            return "clean", text
        if "FOUND" in text:
            return "infected", text
        return "pending_scan", f"resposta inesperada do clamd: {text[:200]}"
