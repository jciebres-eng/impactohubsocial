"""Envio de e-mail transacional.

* ``ConsoleMailer`` (development/test): grava .eml em ``data/outbox`` e registra no log — NÃO envia.
* ``SmtpMailer`` (staging/production): SMTP com STARTTLS obrigatório (porta 587) ou SMTPS (465).
Proibido em produção: console (config.validate).
"""
from __future__ import annotations

import logging
import smtplib
import ssl
import time
import uuid
from email.message import EmailMessage
from pathlib import Path

logger = logging.getLogger("impacto.mail")


def build(sender: str, to: str, subject: str, text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    msg["Message-ID"] = f"<{uuid.uuid4().hex}@impacto>"
    msg.set_content(text)
    return msg


class ConsoleMailer:
    def __init__(self, outbox: Path, sender: str):
        self.outbox, self.sender = outbox, sender
        outbox.mkdir(parents=True, exist_ok=True)

    def send(self, to: str, subject: str, text: str) -> None:
        msg = build(self.sender, to, subject, text)
        name = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}.eml"
        (self.outbox / name).write_bytes(bytes(msg))
        logger.info("email_outbox", extra={"fields": {"to_domain": to.split("@")[-1], "subject": subject, "file": name}})


class SmtpMailer:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str, timeout: int = 15):
        self.host, self.port, self.user, self.password, self.sender, self.timeout = host, port, user, password, sender, timeout

    def send(self, to: str, subject: str, text: str) -> None:
        msg = build(self.sender, to, subject, text)
        ctx = ssl.create_default_context()
        last = None
        for attempt in range(3):
            try:
                if self.port == 465:
                    with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=ctx) as s:
                        if self.user:
                            s.login(self.user, self.password)
                        s.send_message(msg)
                else:
                    with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as s:
                        s.starttls(context=ctx)
                        if self.user:
                            s.login(self.user, self.password)
                        s.send_message(msg)
                return
            except (smtplib.SMTPException, OSError) as exc:
                last = exc
                time.sleep(0.5 * (2 ** attempt))
        raise RuntimeError(f"Falha ao enviar e-mail após 3 tentativas: {type(last).__name__}")
