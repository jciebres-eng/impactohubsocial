"""Value Ledger: registra o valor operacional criado, separado da cobrança.

BILLING ≠ VALUE — a distinção vem textualmente dos documentos desta rodada: "Billing registra
cobrança. Value Ledger registra valor criado."

A DECISÃO QUE DEFINE ESTE MÓDULO

Os documentos dão de exemplo "42 minutos estimados de trabalho automatizado" e "72h estimadas de
trabalho operacional evitadas". Números assim são o que a regra permanente deste projeto proíbe:
não inventar, PROVAR. Então o ledger separa duas coisas:

  * **contagem** — quantas verificações rodaram, quantas lacunas foram achadas, quantos projetos
    foram triados. Isso é MEDIDO: o sistema fez e contou;
  * **estimativa de tempo** — quanto trabalho humano aquilo teria custado. Isso **não** é medido por
    nós e **não** é digitável: vem de `value_baselines`, versionada, com fonte, data e método
    obrigatórios quando há número.

E a consequência de fábrica: as linhas de referência nascem **sem número**. Até alguém declarar com
fonte, `minutes_saved_estimate` é nulo e `estimate_status` é `no_baseline`. Um painel mostrando "72h
economizadas" com número que ninguém conferiu destruiria a credibilidade de todo o resto do produto.

POR QUE A GRAVAÇÃO PASSA POR UMA FUNÇÃO DO BANCO

`app_record_value()` é SECURITY DEFINER e o papel da aplicação **não** tem INSERT em `value_events`.
Mesma razão de `app_record_event()` na v0.16.0: se a aplicação pudesse inserir direto, poderia
escrever a estimativa de tempo à mão — que é exatamente o que não se quer poder fazer.
"""
from __future__ import annotations

import logging
from typing import Any

from ..db.pq import Connection

_LOG = logging.getLogger("impacto.value")

#: Tipos de evento, espelhando `value_event_types`. A lista existe em Python para que o chamador erre
#: em desenvolvimento, e há invariante que a compara com a tabela.
TYPES = (
    "readiness.evaluated", "readiness.gap_found", "match.run_completed", "document.assembled",
    "document.blocked_incomplete", "diagnosis.version_published", "risk.scan_completed",
    "program.projects_screened", "impact_report.accepted", "territorial_gap.computed",
    "ai.analysis_completed",
)
ESTIMATE_STATUS = ("no_baseline", "estimated")


def record(conn: Connection, *, event_type: str, org_id: str, units: int,
           metrics: dict | None = None, project_id: str | None = None,
           program_id: str | None = None, subject_type: str | None = None,
           subject_id: str | None = None, engine_version: str | None = None) -> int | None:
    """Registra valor criado. Nunca levanta: falhar aqui não pode derrubar o trabalho do usuário.

    O Value Ledger é instrumentação. Se a gravação falhar — tipo de evento desconhecido, organização
    removida numa corrida —, a operação que o usuário pediu já aconteceu e deve ser entregue. O que
    não se pode é mentir depois: evento que não gravou não aparece em relatório nenhum.
    """
    if event_type not in TYPES:
        return None
    # SAVEPOINT, e não apenas try/except.
    #
    # Em PostgreSQL, um erro dentro de uma transação a deixa ABORTADA: tudo o que vier depois falha e o
    # COMMIT vira ROLLBACK. Capturar a exceção sem savepoint não protege nada — ao contrário, esconde
    # que o trabalho do usuário foi perdido. Foi exatamente o que aconteceu na primeira versão deste
    # módulo: um erro de tipo na função de preço de IA apagou em silêncio o registro de uso, e o teste
    # que guardava o hash do insumo foi quem denunciou.
    #
    # Com o savepoint, a falha da instrumentação é revertida e só ela.
    conn.run("SAVEPOINT value_ledger")
    try:
        out = conn.scalar(
            "SELECT app_record_value($1,$2,$3,$4,$5,$6,$7,$8,$9)",
            event_type, org_id, int(units), metrics or {}, project_id, program_id,
            subject_type, subject_id, engine_version)
        # O valor acabou de ser registrado; agora se avalia se ALGUMA regra o alcança. Isto não cobra
        # nada: cria candidato com o motivo do estado, de modo que "por que isto não foi cobrado" tenha
        # resposta consultável. Fica no MESMO savepoint, porque promover é parte do mesmo registro.
        if out:
            conn.scalar("SELECT app_promote_billable($1)", out)
    except Exception as exc:  # noqa: BLE001 — instrumentação não derruba a operação do usuário
        conn.run("ROLLBACK TO SAVEPOINT value_ledger")
        # AVISO no log, e não silêncio. O savepoint protege o trabalho do usuário, mas protegeria
        # também um defeito nosso: na primeira versão deste módulo o identificador de uso de IA era
        # passado num campo `uuid`, a gravação era revertida e nenhum evento de valor aparecia — sem
        # nada no log para explicar. Instrumentação que falha calada é como esse defeito sobrevive.
        _LOG.warning("value_ledger_record_failed", extra={
            "event_type": event_type, "org_id": org_id, "error_type": type(exc).__name__})
        return None
    conn.run("RELEASE SAVEPOINT value_ledger")
    return out


def types(conn: Connection) -> list[dict]:
    """O vocabulário, com o que cada unidade significa e qual é a linha de referência vigente.

    A linha de referência vem junto de propósito: quem vê uma estimativa tem direito de ver de onde o
    número saiu, sem precisar pedir.
    """
    return conn.query(
        "SELECT t.key, t.label_pt, t.unit_label, t.what_counts, t.active,"
        " b.minutes_per_unit, b.source_name, b.source_url, b.source_date, b.method_note,"
        " b.effective_from,"
        " (b.minutes_per_unit IS NOT NULL) AS has_baseline"
        " FROM value_event_types t"
        " LEFT JOIN value_baselines b ON b.event_type = t.key AND b.effective_until IS NULL"
        " ORDER BY t.key")


def summary(conn: Connection, *, org_id: str, since: Any = None, program_id: str | None = None) -> dict:
    """Quanto valor o sistema criou para esta organização.

    A resposta separa o que é contagem do que é estimativa, e diz quantos eventos **não** têm
    estimativa — porque "45 minutos economizados" ao lado de "e 300 eventos sem linha de referência"
    é uma afirmação honesta, enquanto o número sozinho não é.
    """
    rows = conn.query(
        "SELECT v.event_type, t.label_pt, t.unit_label, count(*) AS events,"
        " sum(v.units) AS units,"
        " sum(v.minutes_saved_estimate) FILTER (WHERE v.estimate_status = 'estimated') AS minutes,"
        " count(*) FILTER (WHERE v.estimate_status = 'no_baseline') AS events_without_baseline"
        " FROM value_events v JOIN value_event_types t ON t.key = v.event_type"
        " WHERE v.org_id = $1 AND ($2::timestamptz IS NULL OR v.created_at >= $2)"
        "   AND ($3::uuid IS NULL OR v.program_id = $3)"
        " GROUP BY v.event_type, t.label_pt, t.unit_label ORDER BY count(*) DESC",
        org_id, since, program_id)
    minutes = sum(float(r["minutes"] or 0) for r in rows)
    no_base = sum(int(r["events_without_baseline"] or 0) for r in rows)
    return {
        "items": rows,
        "totals": {
            "events": sum(int(r["events"]) for r in rows),
            "units": sum(int(r["units"] or 0) for r in rows),
            # Nomeado como estimativa na própria chave, para que nenhuma tela possa exibi-lo como
            # medição sem ter de reescrever o nome do campo.
            "minutes_saved_estimate": round(minutes, 2) if minutes else None,
            "hours_saved_estimate": round(minutes / 60, 2) if minutes else None,
            "events_without_baseline": no_base,
        },
        "note": ("Contagens de eventos e unidades são MEDIDAS. O tempo é ESTIMATIVA, derivada de "
                 "linhas de referência versionadas com fonte declarada; eventos cujo tipo ainda não "
                 "tem linha de referência aparecem em `events_without_baseline` e não entram no "
                 "total de tempo."),
    }


def feed(conn: Connection, *, org_id: str, event_type: str | None = None, limit: int = 50,
         offset: int = 0) -> dict:
    rows = conn.query(
        "SELECT v.id, v.event_type, t.label_pt, t.unit_label, v.units, v.metrics,"
        " v.minutes_saved_estimate, v.estimate_status, v.engine_version, v.created_at,"
        " v.project_id::text AS project_id, v.program_id::text AS program_id"
        " FROM value_events v JOIN value_event_types t ON t.key = v.event_type"
        " WHERE v.org_id = $1 AND ($2::text IS NULL OR v.event_type = $2)"
        " ORDER BY v.id DESC LIMIT $3 OFFSET $4", org_id, event_type, limit + 1, offset)
    more = len(rows) > limit
    return {"items": rows[:limit], "has_more": more, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------- administração
def set_baseline(conn: Connection, *, event_type: str, minutes_per_unit: float, source_name: str,
                 source_date: Any, method_note: str, source_url: str | None = None,
                 actor: str | None = None) -> dict:
    """Declara a linha de referência de um tipo de evento. Cria VERSÃO nova; não reescreve a anterior.

    Fonte, data e método são obrigatórios — e o CHECK no banco recusa, não só esta função. Sem isso o
    número seria chute com cara de medição, que é o defeito que todo o módulo existe para evitar.
    """
    row = conn.one(
        "INSERT INTO value_baselines(event_type, minutes_per_unit, source_name, source_url,"
        " source_date, method_note, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7)"
        " RETURNING id::text AS id, event_type, minutes_per_unit, effective_from",
        event_type, minutes_per_unit, source_name, source_url, source_date, method_note, actor)
    return row


def set_ai_price(conn: Connection, *, provider: str, model: str, input_per_mtok_cents: float,
                 output_per_mtok_cents: float, source_name: str, source_date: Any,
                 currency: str = "USD", source_url: str | None = None,
                 actor: str | None = None) -> dict:
    """Declara o preço de um modelo. Também versionado, também com fonte obrigatória.

    A tabela nasce **vazia**: nenhum preço de provedor foi inventado no pacote. Enquanto estiver vazia,
    o custo estimado de cada chamada é nulo e `cost_status` diz `no_price_table` — nunca zero, porque
    zero pareceria custo apurado.
    """
    return conn.one(
        "INSERT INTO ai_price_table(provider, model, input_per_mtok_cents, output_per_mtok_cents,"
        " currency, source_name, source_url, source_date, created_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)"
        " RETURNING id::text AS id, provider, model, currency, effective_from",
        provider, model, input_per_mtok_cents, output_per_mtok_cents, currency, source_name,
        source_url, source_date, actor)


def ai_cost_summary(conn: Connection, *, org_id: str | None = None, days: int = 30) -> dict:
    """Custo de IA por organização e por recurso — o insumo da margem por evento de valor.

    `without_price_table` é a parte honesta: enquanto não houver preço declarado para um modelo, as
    chamadas dele aparecem contadas e **fora** do total de custo.
    """
    rows = conn.query(
        "SELECT provider, model, feature, count(*) AS calls,"
        " sum(coalesce(tokens_in,0)) AS tokens_in, sum(coalesce(tokens_out,0)) AS tokens_out,"
        " sum(cost_cents_estimate) FILTER (WHERE cost_status = 'estimated') AS cost_cents,"
        " count(*) FILTER (WHERE cost_status = 'no_price_table') AS without_price_table"
        " FROM ai_usage"
        " WHERE created_at >= now() - make_interval(days => $1)"
        "   AND ($2::uuid IS NULL OR org_id = $2)"
        " GROUP BY provider, model, feature ORDER BY count(*) DESC", days, org_id)
    cost = sum(float(r["cost_cents"] or 0) for r in rows)
    return {
        "items": rows,
        "totals": {
            "calls": sum(int(r["calls"]) for r in rows),
            "cost_cents_estimate": round(cost, 4) if cost else None,
            "calls_without_price_table": sum(int(r["without_price_table"] or 0) for r in rows),
        },
        "note": ("Custo é ESTIMATIVA, calculada dos tokens registrados pela tabela de preço vigente do "
                 "provedor. A tabela nasce vazia: chamadas de modelo sem preço declarado são contadas "
                 "em `calls_without_price_table` e não entram no total."),
    }
