"""Envio de e-mail transacional.

* ``ConsoleMailer`` (development/test): grava .eml em ``data/outbox`` e registra no log — NÃO envia.
* ``SmtpMailer`` (staging/production): SMTP com STARTTLS obrigatório (porta 587) ou SMTPS (465).
Proibido em produção: console (config.validate).

OBSERVABILIDADE (v0.19.0). ``send()`` devolve o resultado da tentativa e, quando um ``on_event`` é
ligado, também o entrega a quem registra em ``email_events``. Antes disso, o identificador da mensagem
era descartado e uma falha de SMTP só existia como linha de log: ninguém conseguia responder "o
provedor está aceitando nossas mensagens?" sem abrir o log do servidor.

VOCABULÁRIO QUE IMPORTA. O estado de sucesso se chama ``accepted_by_smtp``, não ``delivered``. O que
esta camada sabe é que o servidor ACEITOU a mensagem. Entrega só se afirma com retorno do provedor
(webhook de bounce ou de entrega), que esta plataforma ainda não recebe — e chamar aceitação de entrega
seria exatamente o tipo de afirmação sem prova que o produto existe para não fazer.
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


def _domain(to: str) -> str:
    return to.rsplit("@", 1)[-1][:255] or "desconhecido"


class _Base:
    #: recebe um dicionário por tentativa; ligado pelo AppState para gravar em email_events
    on_event = None

    def _emit(self, event: dict) -> None:
        if self.on_event is None:
            return
        try:
            self.on_event(event)
        except Exception:
            # Registrar o envio NÃO pode derrubar o envio: o e-mail de verificação é o que deixa a
            # pessoa entrar na plataforma.
            logger.warning("email_event_record_failed", extra={"fields": {"kind": event.get("kind")}})


class ConsoleMailer(_Base):
    def __init__(self, outbox: Path, sender: str):
        self.outbox, self.sender = outbox, sender
        outbox.mkdir(parents=True, exist_ok=True)

    def send(self, to: str, subject: str, text: str, *, kind: str = "transactional") -> dict:
        inicio = time.monotonic()
        msg = build(self.sender, to, subject, text)
        name = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}.eml"
        (self.outbox / name).write_bytes(bytes(msg))
        logger.info("email_outbox", extra={"fields": {"to_domain": _domain(to), "subject": subject, "file": name}})
        evento = {"message_id": msg["Message-ID"], "kind": kind, "to_domain": _domain(to),
                  "status": "written_to_outbox", "provider": "console", "retry_count": 0,
                  "duration_ms": int((time.monotonic() - inicio) * 1000), "error": None}
        self._emit(evento)
        return evento


class SmtpMailer(_Base):
    def __init__(self, host: str, port: int, user: str, password: str, sender: str, timeout: int = 15):
        self.host, self.port, self.user, self.password, self.sender, self.timeout = host, port, user, password, sender, timeout

    def send(self, to: str, subject: str, text: str, *, kind: str = "transactional") -> dict:
        inicio = time.monotonic()
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
                evento = {"message_id": msg["Message-ID"], "kind": kind, "to_domain": _domain(to),
                          "status": "accepted_by_smtp", "provider": "smtp", "retry_count": attempt,
                          "duration_ms": int((time.monotonic() - inicio) * 1000), "error": None}
                self._emit(evento)
                return evento
            except (smtplib.SMTPException, OSError) as exc:
                last = exc
                time.sleep(0.5 * (2 ** attempt))
        erro = f"{type(last).__name__}: {last}".split("\n")[0][:1000]
        self._emit({"message_id": msg["Message-ID"], "kind": kind, "to_domain": _domain(to),
                    "status": "failed", "provider": "smtp", "retry_count": 3,
                    "duration_ms": int((time.monotonic() - inicio) * 1000), "error": erro})
        raise RuntimeError(f"Falha ao enviar e-mail após 3 tentativas: {type(last).__name__}")
