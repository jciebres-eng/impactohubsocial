"""Território como catálogo: nome resolvido, cadeia, perfil com fonte e o que NÃO se sabe.

O QUE MUDA EM RELAÇÃO AO QUE EXISTIA

Antes da v0.18.0 o território era uma expressão regular (`BR-MT-5105150`) e a hierarquia era derivada
por prefixo de string. Isso respondia "este escopo cobre aquele?" e mais nada. Agora há catálogo, e o
catálogo responde o nome, a cadeia, os indicadores com fonte — e, principalmente, **o que não foi
medido**, com o mesmo destaque do que foi.

A HONESTIDADE DESTA CAMADA ESTÁ EM DUAS COLUNAS

* `from_official_load` separa "achamos que é" de "está no arquivo oficial". País, regiões e as 27 UFs
  nascem com `false`: são conhecimento da plataforma, a conferir na carga. Município só entra por
  importação.
* `measured` no perfil do território: toda definição ativa aparece, com valor quando existe e
  `measured = false` quando não existe. Devolver só o que foi medido daria a impressão de que o resto
  não importa — e é exatamente o resto que explica a lacuna.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection
from ..http import not_found

KINDS = ("international", "country", "region", "state", "municipality")


def search(conn: Connection, *, q: str, kind: str | None = None, uf: str | None = None,
           limit: int = 20) -> dict:
    """Busca por nome ou por código, para preenchimento incremental.

    Casa por texto completo (sem acento, via `pt_unaccent`), por prefixo de nome e por código — quem
    digita "lucas", "Lucas do Rio" ou "5105150" encontra a mesma coisa.
    """
    term = (q or "").strip()
    if len(term) < 2:
        return {"items": [], "note": "digite ao menos dois caracteres"}
    rows = conn.query(
        "SELECT t.code, t.kind, t.name, t.uf, t.ibge_code, t.from_official_load,"
        " territory_label(t.parent_code) AS parent_name,"
        " (SELECT count(*) FROM territory_indicators ti"
        "   WHERE ti.territory = t.code AND ti.effective_until IS NULL) AS indicators"
        " FROM territories t"
        " WHERE t.active"
        "   AND ($2::text IS NULL OR t.kind = $2)"
        "   AND ($3::text IS NULL OR t.uf = $3)"
        "   AND (t.name ILIKE $4 OR t.code ILIKE $4 OR t.ibge_code = $1"
        "        OR to_tsvector('pt_unaccent', t.name) @@ plainto_tsquery('pt_unaccent', $1))"
        " ORDER BY CASE t.kind WHEN 'state' THEN 0 WHEN 'municipality' THEN 1 ELSE 2 END,"
        "          t.name LIMIT $5",
        term, kind, uf.upper() if uf else None, f"%{term}%", limit)
    return {
        "items": rows,
        "note": ("`from_official_load = false` significa linha semeada pela plataforma, a conferir "
                 "na carga do arquivo oficial. O nível municipal só existe depois da importação."),
    }


def profile(conn: Connection, *, code: str) -> dict:
    chain = conn.query("SELECT code, kind, name, known FROM territory_chain($1)", code)
    if not chain:
        raise not_found("Território não encontrado")
    known = any(c["known"] for c in chain)
    rows = conn.query(
        "SELECT p.code, p.name_pt, p.determinant_code, p.unit, p.direction, p.value::float AS value,"
        " p.reference_date, p.source_name, p.source_date, p.measured,"
        " d.name_pt AS determinant_name FROM territory_profile($1) p"
        " JOIN social_determinants d ON d.code = p.determinant_code", code)
    # v0.20.0: procedência completa e FRESCURA do indicador vigente. Até aqui a plataforma sabia
    # dizer que um número não havia sido substituído; não sabia dizer que ele envelheceu — e um
    # indicador de 2010 aparecia com o mesmo peso de um de 2025.
    frescura = {r["code"]: r for r in conn.query(
        "SELECT code, publisher, dataset, dataset_version, license, published_at, retrieved_at,"
        " file_sha256, freshness, months_old, freshness_note FROM territory_indicator_current($1)",
        code)}
    for r in rows:
        extra = frescura.get(r["code"])
        # `extra` existe para todo indicador vigente; a procedência só existe se o número foi
        # ligado a um conjunto de dados. Devolver um bloco de nulos sugeriria procedência vazia em
        # vez de procedência ausente — e são coisas diferentes.
        r["provenance"] = ({k: extra[k] for k in ("publisher", "dataset", "dataset_version",
                                                  "license", "published_at", "retrieved_at",
                                                  "file_sha256")}
                           if extra and extra["publisher"] else None)
        r["freshness"] = (extra or {}).get("freshness", "unknown")
        r["months_old"] = (extra or {}).get("months_old")
        r["freshness_note"] = (extra or {}).get(
            "freshness_note", "indicador não medido para este território")
    measured = [r for r in rows if r["measured"]]
    desatualizados = [r["code"] for r in measured if r["freshness"] == "stale"]
    sem_prazo = [r["code"] for r in measured if r["freshness"] == "undeclared"]
    needs = conn.one(
        "SELECT count(*) AS total, count(*) FILTER (WHERE source_name IS NOT NULL) AS with_source,"
        " count(*) FILTER (WHERE priority = 'critical') AS critical"
        " FROM territory_needs WHERE territory = $1 AND status <> 'archived'", code)
    denominators = conn.query(
        "SELECT kind, value::float AS value, unit, reference_date, source_name, source_date"
        " FROM equity_denominators WHERE scope = 'territory' AND territory = $1"
        "   AND effective_until IS NULL ORDER BY kind", code)
    resumo_frescura = {
        "stale": desatualizados,
        "undeclared": sem_prazo,
        "note": ("Dado DESATUALIZADO é o que passou do prazo declarado pela própria carga. "
                 "`undeclared` significa que ninguém declarou prazo para aquele conjunto — e a "
                 "plataforma responde isso em vez de chamar o dado de atual."),
    }
    return {
        "code": code,
        "label": conn.scalar("SELECT territory_label($1)", code),
        "in_catalog": known,
        "chain": chain,
        "indicators": rows,
        "measured_count": len(measured),
        "definition_count": len(rows),
        "needs": needs,
        "denominators": denominators,
        "freshness": resumo_frescura,
        "note": ("Toda definição ativa aparece, medida ou não: `measured = false` é informação, não "
                 "ausência de informação. Nenhum número foi estimado — cada valor carrega a fonte e "
                 "a data de referência de quem o publicou."
                 + ("" if known else " Este código NÃO está no catálogo territorial: o nome não foi "
                                     "resolvido e a cadeia acima é a derivada do próprio código.")),
    }


def catalog_status(conn: Connection) -> dict:
    """Quão completo está o catálogo. Existe para que a incompletude seja visível, não descoberta."""
    by_kind = conn.query(
        "SELECT kind, count(*) AS total, count(*) FILTER (WHERE from_official_load) AS official"
        " FROM territories WHERE active GROUP BY kind ORDER BY kind")
    inds = conn.one(
        "SELECT count(*) AS values_loaded, count(DISTINCT territory) AS territories_with_data,"
        " count(DISTINCT code) AS indicators_used"
        " FROM territory_indicators WHERE effective_until IS NULL")
    defs = conn.scalar("SELECT count(*) FROM determinant_indicator_defs WHERE active")
    return {
        "by_kind": by_kind,
        "definitions": defs,
        **inds,
        "note": ("O nível municipal e TODO indicador territorial entram por importação de arquivo "
                 "oficial (`scripts/import_territories.py` e "
                 "`scripts/import_territory_indicators.py`), que exigem nome da fonte, URL e data "
                 "de consulta. A plataforma não embute dado do IBGE, do DATASUS nem do INEP: "
                 "transcrever de memória uma lista de 5.570 municípios produziria erros que ninguém "
                 "encontraria, e o código do IBGE é usado para cruzar dado público."),
    }


def definitions(conn: Connection) -> dict:
    rows = conn.query(
        "SELECT d.code, d.determinant_code, s.name_pt AS determinant_name, d.name_pt, d.unit,"
        " d.direction, d.description, d.source_note, d.usual_source"
        " FROM determinant_indicator_defs d JOIN social_determinants s ON s.code = d.determinant_code"
        " WHERE d.active ORDER BY d.determinant_code, d.name_pt")
    return {
        "items": rows,
        "note": ("Lista EDITORIAL da plataforma: a definição e o agrupamento são nossos. "
                 "`usual_source` diz onde o número costuma estar — não afirma que ele já está "
                 "carregado. `direction = context` marca indicador que não é melhor nem pior: "
                 "tratar contexto como desempenho é o erro que aquela coluna evita."),
    }


def set_indicator(conn: Connection, *, territory: str, code: str, value: float,
                  reference_date: Any, source_name: str, source_date: Any,
                  source_url: str | None = None, method_note: str | None = None,
                  dataset_id: str | None = None, actor: str | None = None) -> dict:
    spec = conn.one("SELECT unit FROM determinant_indicator_defs WHERE code = $1 AND active", code)
    if not spec:
        raise not_found("Definição de indicador territorial não encontrada")
    if not conn.one("SELECT 1 FROM territories WHERE code = $1 AND active", territory):
        raise not_found("Território não está no catálogo: importe-o antes de publicar indicador")
    if dataset_id and not conn.one("SELECT 1 FROM external_datasets WHERE id = $1", dataset_id):
        raise not_found("Conjunto de dados não registrado: registre a procedência antes do número")
    return conn.one(
        "INSERT INTO territory_indicators(territory, code, value, unit, reference_date,"
        " source_name, source_url, source_date, method_note, dataset_id, created_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)"
        " RETURNING id::text AS id, territory, code, value::float AS value, unit, reference_date,"
        " source_name, source_date, dataset_id::text AS dataset_id",
        territory, code, value, spec["unit"], reference_date, source_name, source_url, source_date,
        method_note, dataset_id, actor)
