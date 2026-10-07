"""Motor de integridade relacional: órfãos, referências não resolvidas e deriva de catálogo.

O QUE ISTO SUBSTITUI

`scripts/db_integrity_report.py` publicava, como resultado de verificação de órfãos:

    SELECT 'nenhuma verificação de órfão aplicável: toda referência é FK declarada'

Uma string literal, e a afirmação era falsa. Há 25 colunas de referência polimórfica no banco —
`audit_events.object_id`, `ledger_entries.ref_id`, `value_events.subject_id`,
`approval_requests.object_id`, `accounting_entries.source_id` entre elas — e nenhuma pode ter chave
estrangeira, porque aponta para tabelas diferentes conforme o tipo. Eram justamente as referências
que precisavam de verificação, e eram as únicas que não tinham.

TRÊS RELATÓRIOS, TRÊS PERGUNTAS DIFERENTES

* `orphans()`         — há linha apontando para nada?
* `unresolved()`      — há valor de tipo que o motor não sabe resolver? (catálogo atrás do código)
* `catalog_drift()`   — há coluna polimórfica fora do catálogo, ou catalogada e já inexistente?

O terceiro é o que mantém os dois primeiros honestos: um verificador que não percebe quando o
esquema muda devolve "nada a declarar" para sempre.
"""
from __future__ import annotations

from typing import Any


def orphans(c) -> list[dict[str, Any]]:
    return c.query("SELECT source_table, type_column, id_column, type_value, target_table,"
                   "       rows_checked, orphans FROM integrity_orphans()"
                   " ORDER BY orphans DESC, source_table, type_value")


def unresolved(c) -> list[dict[str, Any]]:
    return c.query("SELECT source_table, type_column, type_value, rows_affected"
                   "  FROM integrity_unresolved_refs() ORDER BY rows_affected DESC")


def catalog_drift(c) -> list[dict[str, Any]]:
    return c.query("SELECT source_table, id_column, situation FROM integrity_catalog_drift()")


def chains(c) -> dict[str, Any]:
    """Estado das três cadeias de hash. Conta a verificação, não a existência da coluna."""
    # `org_id IS NOT NULL` importa: eventos de plataforma (interruptor de emergência, por exemplo)
    # são auditados sem organização, e `audit_verify(NULL)` não tem escopo para percorrer.
    trilha = c.query("SELECT o.org_id::text AS org_id, v.entries, v.valid, v.first_broken_seq"
                     "  FROM (SELECT DISTINCT org_id FROM audit_events WHERE org_id IS NOT NULL) o"
                     "  CROSS JOIN LATERAL audit_verify(o.org_id) v")
    ledger = c.query("SELECT p.project_id::text AS project_id, v.entries, v.valid, v.first_broken_seq"
                     "  FROM (SELECT DISTINCT project_id FROM ledger_entries) p"
                     "  CROSS JOIN LATERAL ledger_verify(p.project_id) v")
    valor = c.query("SELECT o.org_id::text AS org_id, v.entries, v.valid, v.first_broken_seq"
                    "  FROM (SELECT DISTINCT org_id FROM value_events WHERE seq IS NOT NULL) o"
                    "  CROSS JOIN LATERAL value_verify(o.org_id) v")
    # Linhas de `value_events` anteriores à v0.23.0 não têm cadeia, e isso é declarado em vez de
    # corrigido: calcular hash para trás produziria uma cadeia que PARECE verificada sem nunca ter
    # protegido nada.
    sem_cadeia = c.scalar("SELECT count(*) FROM value_events WHERE seq IS NULL")
    return {
        "audit": {"scopes": len(trilha), "broken": [t for t in trilha if not t["valid"]]},
        "ledger": {"scopes": len(ledger), "broken": [t for t in ledger if not t["valid"]]},
        "value": {"scopes": len(valor), "broken": [t for t in valor if not t["valid"]],
                  "rows_without_chain": sem_cadeia,
                  "note": "Linhas sem `seq` são anteriores à v0.23.0 e ficam fora da verificação "
                          "de propósito: hash calculado para trás não prova nada."},
    }


def provenance_coverage(c) -> dict[str, Any]:
    """Quantas medições conseguem apontar a própria origem. É o número da regra de proveniência."""
    linha = c.one(
        "SELECT count(*) AS total,"
        "       count(*) FILTER (WHERE evidence_id IS NOT NULL) AS com_evidencia,"
        "       count(*) FILTER (WHERE status = 'validated') AS validadas,"
        "       count(*) FILTER (WHERE status = 'validated' AND evidence_id IS NULL) AS validadas_sem_evidencia,"
        "       count(*) FILTER (WHERE source_kind = 'self_declared') AS autodeclaradas"
        "  FROM indicator_values")
    total = linha["total"] or 0
    return {
        "measurements": total,
        "with_evidence": linha["com_evidencia"],
        "validated": linha["validadas"],
        "validated_without_evidence": linha["validadas_sem_evidencia"],
        "self_declared": linha["autodeclaradas"],
        "coverage_pct": None if not total else round(100.0 * linha["com_evidencia"] / total, 1),
        "rule": "Medição validada EXIGE evidência (indicator_validated_needs_evidence, no banco). "
                "`validated_without_evidence` diferente de zero só é possível por alteração direta "
                "no banco, e é indício de manipulação.",
    }


def report(c) -> dict[str, Any]:
    o, u, d = orphans(c), unresolved(c), catalog_drift(c)
    cad = chains(c)
    quebradas = sum(len(cad[k]["broken"]) for k in ("audit", "ledger", "value"))
    orfas = sum(x["orphans"] for x in o)
    cob = provenance_coverage(c)
    # VERDE só quando não há órfão, nem cadeia quebrada, nem deriva de catálogo, nem medição
    # validada sem evidência. Um relatório que fica verde com ressalva não serve para decidir nada.
    if orfas or quebradas or cob["validated_without_evidence"]:
        estado = "VERMELHO"
    elif d or u:
        estado = "AMARELO"
    else:
        estado = "VERDE"
    return {
        "state": estado,
        "orphan_rows": orfas,
        "broken_chains": quebradas,
        "polymorphic_columns_checked": len({(x["source_table"], x["id_column"]) for x in o}),
        "polymorphic_columns_catalogued": c.scalar("SELECT count(*) FROM polymorphic_refs"),
        "orphans": o,
        "unresolved_refs": u,
        "catalog_drift": d,
        "chains": cad,
        "provenance": cob,
        "note": "AMARELO significa que o catálogo de referências pode estar atrás do esquema — não "
                "que há dado quebrado. VERMELHO é dado quebrado.",
    }
