"""Período gratuito por conta: FULL FREE 2026 e os 3 meses das assinaturas novas de 2027.

POR QUE A GRATUIDADE É UM REGISTRO, E NÃO UMA DATA NO CÓDIGO

A regra comercial cabe numa frase — "tudo grátis até 31/12/2026, e toda assinatura nova a partir
de 2027 ganha 3 meses" — e é justamente por isso que a implementação óbvia está errada. Uma
constante comparada com `now()` responde "estamos antes de 2027?". Ninguém faz essa pergunta. As
perguntas reais são: *esta conta* está gratuita? até quando? por quê? quem concedeu? o que ela
aceitou? E uma constante não sabe nada sobre uma conta.

Então cada conta tem a sua linha em `free_periods`, com origem, motivo, versão de preço e autor.
A campanha de 2026 é o que CONCEDE essas linhas — não o que as substitui.

MESES DE CALENDÁRIO, NÃO 90 DIAS

"3 meses" aqui significa 3 meses de calendário (ver `FULL_FREE_2026.md` §3 e ADR-268). Quem assina
dia 15 espera que acabe dia 15. Noventa dias quebram essa expectativa em todo trimestre que
contenha um mês de 31 dias — e quebram para menos, o que o cliente percebe.

`ends_at` É EXCLUSIVO: o período é [started_at, ends_at).
"""
from __future__ import annotations

import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[3] / "config" / "plans.json"

SOURCES = ("2026_CAMPAIGN", "2027_NEW_SUBSCRIPTION", "PROMOTION", "GRANT", "PARTNERSHIP",
           "MANUAL_EXCEPTION")

# Quantos meses de calendário uma assinatura nova recebe a partir de 2027.
NEW_SUBSCRIPTION_MONTHS = 3

# Estados comerciais que `org_commercial_state()` devolve. A lista vive aqui para que a API e a
# interface tenham um lugar só para conferir, e para que acrescentar um estado novo sem avisar
# ninguém quebre o teste em vez de aparecer como rótulo vazio na tela.
STATES = ("FREE", "FREE_EXPIRING", "PAYMENT_METHOD_REQUIRED", "COMMERCIAL_TERM_PENDING",
          "PAID_ACTIVE", "CANCELLED", "SUSPENDED", "PAST_DUE", "GRACE_PERIOD", "TERMINATED")


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
          ends_at=None, subscription_id: str | None = None, plan_key: str | None = None,
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
        "INSERT INTO free_periods(org_id, subscription_id, source, reason, pricing_version,"
        " plan_key, months, started_at, ends_at, granted_by, status)"
        # Os casts não são decoração: `$7` entra como smallint na coluna `months` e como integer
        # no argumento de `add_calendar_months`, e o servidor recusa deduzir dois tipos para o
        # mesmo parâmetro. Dizer o tipo é mais barato do que descobrir isso em produção.
        " VALUES ($1,$2,$3,$4,$5,$6,$7::smallint, coalesce($8::timestamptz, now()),"
        "         coalesce($9::timestamptz,"
        "                  add_calendar_months(coalesce($8::timestamptz, now()), $7::int)),"
        "         $10, 'active')"
        " ON CONFLICT DO NOTHING"
        " RETURNING id::text, started_at, ends_at, source, months",
        org_id, subscription_id, source, reason, pricing_version(), plan_key, months,
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


def grant_new_subscription(c, *, org_id: str, subscription_id: str,
                           plan_key: str | None = None) -> dict | None:
    """Concede os 3 meses de calendário de uma assinatura nova.

    Só a partir de 2027: enquanto a campanha de 2026 estiver valendo, a conta JÁ está gratuita, e
    empilhar três meses em cima disso daria ao cliente que assinou em dezembro quase quinze meses
    de graça enquanto quem assinou em janeiro teria três. O benefício começa quando a gratuidade
    geral termina.
    """
    if campaign_2026_open(c):
        return None
    return grant(
        c, org_id=org_id, source="2027_NEW_SUBSCRIPTION", subscription_id=subscription_id,
        plan_key=plan_key, months=NEW_SUBSCRIPTION_MONTHS,
        reason=f"{NEW_SUBSCRIPTION_MONTHS} meses de calendário gratuitos para assinatura nova, "
               f"conforme PRICING_BIBLE.md §4.2.")


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
    90: "Seu período gratuito termina em 90 dias",
    60: "Seu período gratuito termina em 60 dias",
    30: "Seu período gratuito termina em 30 dias",
    7:  "Seu período gratuito termina em 7 dias",
    1:  "Seu período gratuito termina amanhã",
}


def _body(dias: int, autorizado: bool) -> str:
    if autorizado:
        return (f"Faltam {dias} dia(s). Como você já autorizou a cobrança, a assinatura segue "
                "automaticamente e a primeira fatura sai no fim do período gratuito. "
                "Você pode cancelar antes disso, sem custo.")
    # A frase que mais importa do arquivo inteiro: não fazer nada é uma opção segura.
    return (f"Faltam {dias} dia(s). Você NÃO será cobrado: nenhuma cobrança foi autorizada. "
            "Se não fizer nada, sua conta continua no plano gratuito, sem perder dados. "
            "Para continuar com os recursos pagos, autorize a cobrança antes do fim do período.")


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
                           f"Seu período gratuito termina em {dias} dias",
                           _body(dias, r["auth"])):
                enviados += 1
    return {"notified": enviados}


def sweep(c) -> dict:
    """Marca como expirados os períodos que terminaram. Não cobra, não suspende, não apaga.

    O fim de um período gratuito devolve a conta ao plano gratuito permanente. É a única coisa que
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
                        "Seu período gratuito terminou",
                        "Sua conta voltou ao plano gratuito. Nenhuma cobrança foi feita e nenhum "
                        "dado foi apagado. Os recursos pagos ficam disponíveis assim que você "
                        "autorizar a cobrança.")
    out = {"expired": len(encerrados)}
    out.update(notify_windows(c))
    return out
