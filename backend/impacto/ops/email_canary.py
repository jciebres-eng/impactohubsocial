"""Canário de e-mail: descobrir que o envio parou ANTES de a pessoa não conseguir entrar.

O RISCO CONCRETO. O cadastro depende do e-mail de verificação. Se a credencial do SMTP expirar, o
provedor bloquear o remetente ou a porta fechar, o funil de entrada vai a zero — e o produto continua
respondendo 202 em `/v1/auth/register`, como se tudo estivesse bem. A primeira pessoa a saber seria
alguém que não conseguiu entrar e não reclamou.

O QUE O CANÁRIO AFIRMA E O QUE NÃO AFIRMA. Ele envia uma mensagem de verdade para um endereço de
monitoramento e registra o resultado. Sucesso aqui significa ACEITAÇÃO PELO SERVIDOR SMTP — e o estado
se chama exatamente isso. Entrega de verdade exige retorno do provedor (webhook de bounce/entrega),
que a plataforma ainda não recebe; afirmar entrega com base em aceitação seria inventar prova.
"""
from __future__ import annotations

from datetime import UTC, datetime

from ..db.pq import Connection
from . import runs

JOB = "email_canary"


def configured(settings) -> tuple[bool, str]:
    if not settings.email_canary_to:
        return False, "EMAIL_CANARY_TO não definido"
    return True, ""


def recent_failures(conn: Connection, *, minutes: int = 60) -> dict:
    """Falhas de envio na janela, por tipo de mensagem. É o que o alerta observa."""
    rows = conn.query(
        "SELECT kind, count(*) FILTER (WHERE status = 'failed') AS falhas, count(*) AS total"
        "  FROM email_events WHERE at > now() - make_interval(mins => $1::int)"
        " GROUP BY kind ORDER BY falhas DESC, kind", minutes)
    return {"window_minutes": minutes, "by_kind": rows,
            "failed": sum(r["falhas"] for r in rows), "total": sum(r["total"] for r in rows)}


def run(conn: Connection, app, *, force: bool = False) -> dict:
    settings = app.settings
    ok, motivo = configured(settings)
    if not ok:
        with runs.record(conn, JOB) as r:
            r["status"] = "not_configured"
            r["detail"] = {"reason": motivo,
                           "note": ("Dependência externa: endereço de monitoramento é decisão de "
                                    "operação. Sem canário, falha de envio só aparece por reclamação.")}
        return {"status": "not_configured", "reason": motivo}

    intervalo = max(1, int(settings.email_canary_interval_minutes)) * 60
    if not force and not runs.due(conn, JOB, every_seconds=intervalo):
        return {"status": "skipped", "reason": "fora da janela"}

    with runs.record(conn, JOB) as r:
        marca = datetime.now(UTC).isoformat(timespec="seconds")
        evento = app.mailer.send(
            settings.email_canary_to,
            "[Impacto] canário de e-mail",
            "Mensagem automática de monitoramento. Se ela parar de chegar, o envio de e-mail da "
            f"plataforma parou — e com ele o cadastro de novas contas.\nCarimbo: {marca}\n",
            kind="canary")
        falhas = recent_failures(conn, minutes=max(60, settings.email_canary_interval_minutes))
        r["status"] = "ok"
        r["detail"] = {
            "provider": evento["provider"], "status": evento["status"],
            "message_id": evento["message_id"], "retry_count": evento["retry_count"],
            "duration_ms": evento["duration_ms"], "stamp": marca,
            "recent_failures": falhas["failed"], "recent_total": falhas["total"],
            "note": ("accepted_by_smtp é aceitação pelo servidor, NÃO entrega. Entrega exige retorno "
                     "do provedor, que a plataforma ainda não recebe."),
        }
        resultado = dict(r["detail"], status="ok")
    return resultado
