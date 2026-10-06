"""Motor de Qualidade de Dado: sete achados, e uma regra que vale mais que os sete.

A REGRA QUE VALE MAIS QUE OS SETE (§69, textual): **não transformar baixa qualidade de dados
automaticamente em baixa performance do projeto.**

É a regra mais fácil de quebrar sem perceber. Um projeto numa periferia sem dado público, tocado por
três pessoas que anotam no caderno, produz dado incompleto. Um projeto de uma fundação com equipe de
monitoramento produz dado completo. Se a qualidade do dado entrar na nota, a plataforma conclui que o
segundo tem mais impacto — e terá medido orçamento de monitoramento, não impacto. Fazer isso uma vez
é o suficiente para a plataforma inverter exatamente a desigualdade que ela existe para enxergar.

Então aqui a saída é deliberadamente SEPARADA: achados de qualidade saem com `about: "the_data"` e
nunca com `about: "the_project"`, não há nota agregada, não há faixa, e nada que sai daqui alimenta
reputação, selo ou compatibilidade. Há teste para cada uma dessas quatro coisas.

OS SETE ACHADOS (§69), cada um com uma pergunta que ele responde

missing        O que foi declarado e não foi preenchido. (indicador sem nenhum valor; marco sem prazo)
duplicate      O mesmo fato contado duas vezes. (duas medições do mesmo indicador na mesma data)
inconsistent   Dois números que não fecham entre si. (soma dos marcos acima do orçamento declarado)
stale          O dado parou no tempo. (nenhuma medição há mais de um ano num projeto em execução)
invalid        O valor não cabe na unidade declarada. (percentual acima de 100, valor negativo)
contradictory  Dois registros que afirmam coisas opostas. (mesma data, mesmo indicador, valores
               diferentes — alguém corrigiu sem retirar o anterior)
unverifiable   A afirmação não tem como ser conferida. (valor validado sem evidência anexada)

CADA ACHADO APONTA PARA UMA LINHA. Achado sem `ref_id` seria opinião sobre o projeto, que é
exatamente o que este motor não produz.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection

ENGINE_VERSION = "data-quality@1.0.0"

KINDS = ("missing", "duplicate", "inconsistent", "stale", "invalid", "contradictory",
         "unverifiable")

KIND_LABEL = {
    "missing": "não preenchido",
    "duplicate": "contado duas vezes",
    "inconsistent": "não fecha com outro número",
    "stale": "parado no tempo",
    "invalid": "fora da unidade declarada",
    "contradictory": "dois registros se contradizem",
    "unverifiable": "sem como conferir",
}

#: A frase que impede o uso errado. Sai na resposta, em toda chamada.
NOT_PERFORMANCE = (
    "ISTO NÃO É AVALIAÇÃO DO PROJETO. São achados sobre o DADO declarado, e nada aqui alimenta "
    "reputação, selo, compatibilidade ou qualquer nota. Projeto em território sem dado público "
    "produz dado incompleto; transformar isso em desempenho baixo faria a plataforma medir "
    "orçamento de monitoramento e chamar o resultado de impacto."
)


def _f(kind: str, ref_type: str, ref_id: str, what: str, *, detail: str | None = None) -> dict:
    return {"kind": kind, "label": KIND_LABEL[kind], "about": "the_data",
            "ref_type": ref_type, "ref_id": str(ref_id), "what": what, "detail": detail}


def assess(conn: Connection, *, project_id: str) -> dict[str, Any]:
    """Os sete achados sobre o dado declarado de um projeto. Nenhuma nota, nenhuma faixa."""
    projeto = conn.one(
        "SELECT id::text AS id, status, budget_total_cents, beneficiaries_count, starts_on,"
        " ends_on FROM projects WHERE id = $1", project_id)
    if not projeto:
        from ..http import not_found
        raise not_found("Projeto")

    achados: list[dict] = []

    # ---- missing: indicador declarado e nunca medido; marco sem prazo
    for r in conn.query(
            "SELECT pi.id::text AS id, coalesce(ic.name, 'indicador') AS nome"
            " FROM project_indicators pi LEFT JOIN indicator_catalog ic ON ic.id = pi.indicator_id"
            " WHERE pi.project_id = $1 AND NOT EXISTS ("
            "   SELECT 1 FROM indicator_values v WHERE v.project_indicator_id = pi.id)", project_id):
        achados.append(_f("missing", "project_indicator", r["id"],
                          f"Indicador '{r['nome']}' foi declarado e nunca medido."))
    for r in conn.query("SELECT id::text AS id, title FROM milestones"
                        " WHERE project_id = $1 AND due_on IS NULL", project_id):
        achados.append(_f("missing", "milestone", r["id"],
                          f"Marco '{r['title']}' não tem prazo declarado.",
                          detail="Sem prazo, não há como avisar antes do vencimento."))

    # ---- duplicate: duas medições do mesmo indicador na mesma data
    for r in conn.query(
            "SELECT min(v.id::text) AS id, v.project_indicator_id::text AS pi, v.measured_on,"
            " count(*) AS n FROM indicator_values v WHERE v.project_id = $1"
            " GROUP BY v.project_indicator_id, v.measured_on HAVING count(*) > 1", project_id):
        achados.append(_f("duplicate", "indicator_value", r["id"],
                          f"{r['n']} medições do mesmo indicador em {r['measured_on']}.",
                          detail="Somar as duas contaria o mesmo fato duas vezes."))

    # ---- contradictory: mesma data, mesmo indicador, valores DIFERENTES
    for r in conn.query(
            "SELECT min(v.id::text) AS id, v.measured_on, count(DISTINCT v.value) AS valores"
            " FROM indicator_values v WHERE v.project_id = $1"
            " GROUP BY v.project_indicator_id, v.measured_on"
            " HAVING count(DISTINCT v.value) > 1", project_id):
        achados.append(_f("contradictory", "indicator_value", r["id"],
                          f"{r['valores']} valores diferentes para o mesmo indicador em "
                          f"{r['measured_on']}.",
                          detail="Alguém corrigiu sem retirar o anterior: os dois continuam valendo."))

    # ---- inconsistent: soma dos marcos acima do orçamento declarado
    soma = conn.scalar("SELECT coalesce(sum(amount_cents), 0) FROM milestones"
                       " WHERE project_id = $1 AND status <> 'rejected'", project_id)
    if projeto["budget_total_cents"] and soma and soma > projeto["budget_total_cents"]:
        achados.append(_f("inconsistent", "project", project_id,
                          f"A soma dos marcos (R$ {soma / 100:,.2f}) passa do orçamento declarado "
                          f"(R$ {projeto['budget_total_cents'] / 100:,.2f}).",
                          detail="Um dos dois números está errado; a plataforma não escolhe qual."))

    # ---- invalid: percentual fora de 0..100, ou valor negativo em unidade que não admite
    for r in conn.query(
            "SELECT v.id::text AS id, v.value::float AS valor, ic.unit, ic.name"
            " FROM indicator_values v JOIN project_indicators pi ON pi.id = v.project_indicator_id"
            " JOIN indicator_catalog ic ON ic.id = pi.indicator_id"
            " WHERE v.project_id = $1 AND ("
            "   (ic.unit ILIKE '%%percent%%' OR ic.unit = '%%' OR ic.unit ILIKE '%%porcent%%')"
            "    AND (v.value < 0 OR v.value > 100)"
            "   OR (ic.unit ILIKE '%%pessoa%%' AND v.value < 0))", project_id):
        achados.append(_f("invalid", "indicator_value", r["id"],
                          f"Valor {r['valor']} não cabe na unidade declarada ({r['unit']}) do "
                          f"indicador '{r['name']}'."))

    # ---- stale: projeto em execução e nenhuma medição no último ano
    ultima = conn.scalar("SELECT max(measured_on) FROM indicator_values WHERE project_id = $1",
                         project_id)
    if projeto["status"] in ("in_execution", "published", "funded") and projeto["id"]:
        if ultima is None:
            achados.append(_f("missing", "project", project_id,
                              "Projeto em andamento sem nenhuma medição registrada."))
        elif conn.scalar("SELECT $1::date < current_date - interval '1 year'", ultima):
            achados.append(_f("stale", "project", project_id,
                              f"A medição mais recente é de {ultima}.",
                              detail="Dado parado não é dado ruim: pode ser que ninguém tenha "
                                     "medido, e isso é diferente de ter medido mal."))

    # ---- unverifiable: valor VALIDADO sem evidência anexada
    for r in conn.query(
            "SELECT id::text AS id, measured_on FROM indicator_values"
            " WHERE project_id = $1 AND status = 'validated' AND evidence_id IS NULL", project_id):
        achados.append(_f("unverifiable", "indicator_value", r["id"],
                          f"Valor de {r['measured_on']} consta validado e não tem evidência "
                          "anexada.",
                          detail="Validação sem evidência é confiança, não verificação."))

    por_tipo = {k: sum(1 for a in achados if a["kind"] == k) for k in KINDS}
    return {
        "project_id": project_id,
        "engine_version": ENGINE_VERSION,
        "findings": achados,
        "by_kind": por_tipo,
        "total": len(achados),
        # Deliberadamente NÃO existe: score, band, grade, percentual de qualidade. Ver NOT_PERFORMANCE.
        "not_a_performance_score": NOT_PERFORMANCE,
        "note": ("Cada achado aponta para uma LINHA que a organização pode abrir e corrigir. "
                 "Achado sem referência seria opinião sobre o projeto — que é precisamente o que "
                 "este motor não produz. Nenhum achado é falha moral: 'parado no tempo' pode "
                 "significar que ninguém mediu, o que é diferente de ter medido mal."),
    }


def vocabulary() -> dict[str, Any]:
    return {"kinds": [{"key": k, "label": KIND_LABEL[k]} for k in KINDS],
            "not_a_performance_score": NOT_PERFORMANCE}
