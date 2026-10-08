"""Período de concessão por conta: FULL FREE 2026 e concessões temporais (promoção, parceria, exceção).

v0.27.0 (ADR-341): NÃO EXISTE ASSINATURA. O acesso ao núcleo é gratuito por desenho, não por prazo. Um
período de concessão responde outra pergunta: "esta conta tem, por tempo determinado, capacidades que
normalmente viriam de um contrato?" — e até quando, por quê, concedido por quem. A origem
`2027_NEW_SUBSCRIPTION` (3 meses de assinatura nova) foi aposentada junto com a assinatura.

POR QUE A CONCESSÃO É UM REGISTRO, E NÃO UMA DATA NO CÓDIGO

Uma constante comparada com `now()` responde "estamos antes de 2027?". Ninguém faz essa pergunta. As
perguntas reais são: *esta conta* tem concessão? até quando? por quê? quem concedeu? E uma constante
não sabe nada sobre uma conta. Então cada conta tem a sua linha em `free_periods`, com origem, motivo,
versão de preço e autor. A campanha de 2026 é o que CONCEDE essas linhas — não o que as substitui.

MESES DE CALENDÁRIO, NÃO 90 DIAS (ADR-268). `ends_at` É EXCLUSIVO: o período é [started_at, ends_at).
"""
from __future__ import annotations

import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[3] / "config" / "plans.json"

SOURCES = ("2026_CAMPAIGN", "PROMOTION", "GRANT", "PARTNERSHIP", "MANUAL_EXCEPTION")

# Estados comerciais que `org_commercial_state()` devolve (v0.27.0): a pergunta é "de onde vem o acesso?".
# A lista vive aqui para que a API e a interface tenham um lugar só para conferir, e para que acrescentar
# um estado novo sem avisar ninguém quebre o teste em vez de aparecer como rótulo vazio na tela.
STATES = ("FREE_ACCESS", "FREE_GRANT", "GRANT_EXPIRING", "CONTRACTED")
STATE_LABEL = {"FREE_ACCESS": "Acesso livre ao núcleo (gratuito por desenho)",
               "FREE_GRANT": "Concessão temporal vigente",
               "GRANT_EXPIRING": "Concessão termina em até 30 dias (aviso, nunca cobrança)",
               "CONTRACTED": "Contrato comercial aceito com autorização de cobrança"}


def pricing_version() -> str:
    """A versão de preço vigente, lida da configuração — nunca escrita em dois lugares."""
    return json.loads(CONFIG.read_text(encoding="utf-8")).get("pricing_version") or "unversioned"


def campaign_2026_open(c) -> bool:
    """A campanha de 2026 ainda está valendo?

    Perguntado ao BANCO, não ao processo: o relógio do servidor de aplicação e o do banco podem
    discordar, e a fronteira comercial é uma só. Toda data desta camada vem de `now()` do banco.
    """
    return bool(c.scalar("SELECT full_free_2026_ends_at() > now()"))


def grant(c, *, org_id: str, source: str, reason: str, months: int | None = None,
          ends_at=None, plan_key: str | None = None,
          granted_by: str | None = None, starts_at=None) -> dict | None:
    """Concede um período gratuito. Devolve o registro, ou None se a conta já tinha aquele.

    Ou `months` (meses de calendário a partir do início) ou `ends_at` (instante fixo). Pedir os
    dois seria pedir à função que escolhesse qual obedecer.
    """
    if source not in SOURCES:
        raise ValueError(f"origem desconhecida de período gratuito: {source!r}")
    if (months is None) == (ends_at is None):
        raise ValueError("informe meses de calendário OU uma data de fim, nunca ambos")

    row = c.one(
        "INSERT INTO free_periods(org_id, source, reason, pricing_version,"
        " plan_key, months, started_at, ends_at, granted_by, status)"
        # Os casts não são decoração: `$6` entra como smallint na coluna `months` e como integer
        # no argumento de `add_calendar_months`, e o servidor recusa deduzir dois tipos para o
        # mesmo parâmetro. Dizer o tipo é mais barato do que descobrir isso em produção.
        " VALUES ($1,$2,$3,$4,$5,$6::smallint, coalesce($7::timestamptz, now()),"
        "         coalesce($8::timestamptz,"
        "                  add_calendar_months(coalesce($7::timestamptz, now()), $6::int)),"
        "         $9, 'active')"
        " ON CONFLICT DO NOTHING"
        " RETURNING id::text, started_at, ends_at, source, months",
        org_id, source, reason, pricing_version(), plan_key, months,
        starts_at, ends_at, granted_by)
    return dict(row) if row else None


def grant_campaign_2026(c, *, org_id: str) -> dict | None:
    """Concede a campanha FULL FREE 2026 a uma conta recém-criada.

    Fora da janela da campanha isto NÃO FAZ NADA — e é de propósito. Uma conta criada em março de
    2027 não recebe "o resto de 2026"; ela recebe o que a regra de 2027 der, se assinar.
    """
    if not campaign_2026_open(c):
        return None
    return grant(
        c, org_id=org_id, source="2026_CAMPAIGN",
        reason="FULL FREE 2026 — produto integralmente gratuito até 31/12/2026 "
               "(America/Sao_Paulo), por decisão do proprietário registrada em PRICING_BIBLE.md §4.1.",
        ends_at=c.scalar("SELECT full_free_2026_ends_at()"))


def state(c, org_id: str) -> dict:
    """O estado comercial da conta, do jeito que a API e a interface precisam ler.

    FREE_PERIOD_END sai DAQUI e de lugar nenhum mais. A interface não calcula essa data: a classe
    inteira de defeito em que a tela mostra um prazo e a cobrança usa outro só existe quando duas
    camadas fazem a mesma conta.
    """
    row = c.one(
        "SELECT org_commercial_state($1) AS state, free_period_end($1) AS free_period_end,"
        " EXISTS (SELECT 1 FROM offer_acceptances WHERE org_id = $1"
        "         AND consent_status = 'authorized' AND revoked_at IS NULL) AS charge_authorized",
        org_id)
    out = dict(row) if row else {"state": "FREE", "free_period_end": None,
                                 "charge_authorized": False}
    fim = out.get("free_period_end")
    out["days_remaining"] = c.scalar(
        "SELECT greatest(0, ceil(extract(epoch FROM ($1::timestamptz - now())) / 86400))::int",
        fim) if fim else None
    out["periods"] = [dict(r) for r in c.query(
        "SELECT source, reason, months, started_at, ends_at, status FROM free_periods"
        " WHERE org_id = $1 AND status <> 'cancelled' ORDER BY ends_at DESC", org_id)]
    return out


def cancel(c, *, period_id: str, cancelled_by: str | None, reason: str) -> bool:
    """Cancela um período gratuito concedido. O registro FICA — cancelado, com motivo e autor.

    Apagar a linha apagaria a prova de que a plataforma concedeu, que é exatamente o que o cliente
    invocaria se discordasse do cancelamento.
    """
    return bool(c.one(
        "UPDATE free_periods SET status = 'cancelled', cancelled_at = now(), cancelled_by = $2,"
        " cancel_reason = $3 WHERE id = $1 AND status = 'active' RETURNING 1 AS ok",
        period_id, cancelled_by, reason))


# AVISOS COMERCIAIS. As cinco janelas exigidas, mais o lembrete semanal nos últimos 30 dias.
#
# Avisar cedo é o que separa "a gratuidade acabou" de "fui pego de surpresa". Noventa dias é tempo
# de orçar; um dia é tempo de decidir. Nenhuma janela cobra nada — elas avisam, e a conta que não
# fizer nada continua funcionando no plano gratuito.
WINDOWS = (90, 60, 30, 7, 1)
WEEKLY_FROM = 30     # a partir de quantos dias restantes entra também o lembrete semanal

_TITLES = {
    90: "Sua concessão termina em 90 dias",
    60: "Sua concessão termina em 60 dias",
    30: "Sua concessão termina em 30 dias",
    7:  "Sua concessão termina em 7 dias",
    1:  "Sua concessão termina amanhã",
}


def _body(dias: int, autorizado: bool) -> str:
    if autorizado:
        return (f"Faltam {dias} dia(s) de concessão. Como há contrato aceito com autorização de cobrança, "
                "as capacidades do contrato continuam após o fim da concessão, conforme o contrato.")
    # A frase que mais importa do arquivo inteiro: não fazer nada é uma opção segura.
    return (f"Faltam {dias} dia(s) de concessão. Você NÃO será cobrado: não existe assinatura. "
            "Se não fizer nada, sua conta continua com o acesso livre ao núcleo, sem perder dados. "
            "Capacidades contratuais seguem por concessão, convênio ou contrato.")


def notify_windows(c) -> dict:
    """Dispara os avisos de fim de período gratuito. Um aviso por janela, por período.

    A idempotência é de `notify_once` (chave `billing_notices`), então rodar o job dez vezes no
    mesmo dia manda um aviso só — o que importa quando o job é reexecutado depois de uma falha.
    """
    from .monetization import notify_once
    enviados = 0
    for r in c.query(
            "SELECT f.id::text AS id, f.org_id::text AS org_id,"
            "       ceil(extract(epoch FROM (f.ends_at - now())) / 86400)::int AS dias,"
            "       EXISTS (SELECT 1 FROM offer_acceptances a WHERE a.org_id = f.org_id"
            "               AND a.consent_status = 'authorized' AND a.revoked_at IS NULL) AS auth"
            "  FROM free_periods f"
            " WHERE f.status = 'active' AND f.ends_at > now()"
            # Só o período que termina DEPOIS manda aviso: avisar pelo que acaba primeiro quando
            # existe outro em seguida assustaria o cliente com um prazo que não é o dele.
            "   AND f.ends_at = (SELECT max(g.ends_at) FROM free_periods g"
            "                     WHERE g.org_id = f.org_id AND g.status = 'active')"):
        dias = int(r["dias"])
        if dias in WINDOWS:
            if notify_once(c, r["org_id"], "free_period_ending", f"{r['id']}:d{dias}",
                           _TITLES[dias], _body(dias, r["auth"])):
                enviados += 1
        elif dias <= WEEKLY_FROM and dias % 7 == 0:
            if notify_once(c, r["org_id"], "free_period_ending", f"{r['id']}:w{dias}",
                           f"Sua concessão termina em {dias} dias",
                           _body(dias, r["auth"])):
                enviados += 1
    return {"notified": enviados}


def sweep(c) -> dict:
    """Marca como expirados os períodos que terminaram. Não cobra, não suspende, não apaga.

    O fim de uma concessão devolve a conta ao acesso livre do núcleo. É a única coisa que
    acontece — e dizer isso em código é mais barato do que explicar depois por que a conta de
    alguém foi suspensa.
    """
    encerrados = [dict(r) for r in c.query(
        "UPDATE free_periods SET status = 'expired'"
        " WHERE status = 'active' AND ends_at <= now()"
        " RETURNING id::text, org_id::text AS org_id")]
    from .monetization import notify_once
    for r in encerrados:
        # Avisar o FIM também, e não só a aproximação: é o momento em que o cliente percebe a
        # mudança, e é quando ele mais precisa ouvir que nada foi cobrado e nada foi apagado.
        if not c.one("SELECT 1 FROM free_periods WHERE org_id = $1 AND status = 'active'"
                     " AND ends_at > now()", r["org_id"]):
            notify_once(c, r["org_id"], "free_period_ended", r["id"],
                        "Sua concessão terminou",
                        "Sua conta segue com o acesso livre ao núcleo. Nenhuma cobrança foi feita e nenhum "
                        "dado foi apagado. Capacidades contratuais voltam por concessão, convênio ou contrato.")
    out = {"expired": len(encerrados)}
    out.update(notify_windows(c))
    return out
