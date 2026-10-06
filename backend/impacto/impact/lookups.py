"""Busca incremental com PROCEDÊNCIA declarada em cada sugestão.

A regra que organiza este módulo, e que vem dos documentos desta rodada: **sugestão sem origem é
sugestão que o usuário não pode avaliar.** Então toda linha devolvida carrega:

* `origin` — de onde veio: carga oficial, lista editorial da plataforma, ou o histórico da própria
  organização;
* `origin_label` — a mesma coisa em português, para a interface não ter de traduzir;
* `source_name` / `source_date` — quando existem;
* `verified` — se houve ato de terceiro por trás daquela linha.

A segunda regra está na interface e é mais importante que esta: **sugestão nunca sobrescreve o que a
pessoa escreveu em silêncio.** O componente `Suggest` (web/src/ui/suggest.tsx) mantém o texto
digitado como verdade e pede confirmação para substituir.

Nada daqui é busca livre no banco: cada chave é uma consulta escrita à mão, com colunas escolhidas.
Busca genérica parametrizável seria um caminho para ler o que não deve.
"""
from __future__ import annotations

from ..db.pq import Connection
from ..http import unprocessable

ORIGIN_LABEL = {
    "official_load": "carga oficial (com fonte e data)",
    "platform_knowledge": "conhecimento da plataforma — conferir na carga oficial",
    "platform_editorial": "lista editorial da plataforma",
    "your_organization": "histórico da sua organização",
    "another_organization": "declarado por outra organização",
}

#: Cada entrada declara o que devolve e de onde. A ordem é a de utilidade para quem preenche.
CATALOG = [
    ("territories", "Territórios", "Unidade da federação, região e município quando carregado.",
     ("official_load", "platform_knowledge")),
    ("ods", "Objetivos de Desenvolvimento Sustentável", "Os 17 objetivos, por número e nome.",
     ("platform_knowledge",)),
    ("ods_targets", "Metas dos ODS", "Metas oficiais JÁ CARREGADAS (podem ser zero).",
     ("official_load",)),
    ("indicators", "Indicadores", "Catálogo de indicadores com unidade e dimensão.",
     ("platform_editorial", "your_organization")),
    ("equity_barriers", "Barreiras de acesso", "Catálogo editorial de barreiras de equidade.",
     ("platform_editorial",)),
    ("determinants", "Determinantes sociais", "Definições de indicador de determinante social.",
     ("platform_editorial",)),
    ("materiality_topics", "Temas de materialidade", "Temas candidatos, por dimensão.",
     ("platform_editorial",)),
    ("frameworks", "Referenciais de impacto", "Registro de referenciais e o que a plataforma faz "
     "com cada um.", ("platform_editorial",)),
    ("seal_rules", "Critérios de selo", "Conjunto fechado de critérios implementados.",
     ("platform_editorial",)),
    ("beneficiary_groups", "Grupos de beneficiários", "Taxonomia com política de uso declarada.",
     ("platform_editorial",)),
    ("legal_natures", "Naturezas jurídicas", "Itens de catálogo institucional publicados.",
     ("platform_editorial",)),
    ("my_suppliers", "Fornecedores que já usei", "Do histórico de despesas da sua organização.",
     ("your_organization",)),
    ("my_projects", "Meus projetos", "Projetos da sua organização.", ("your_organization",)),
]
KEYS = {k for k, _l, _d, _o in CATALOG}


def catalog() -> dict:
    return {
        "items": [{"key": k, "label": label, "returns": desc,
                   "origins": [{"key": o, "label": ORIGIN_LABEL[o]} for o in origins]}
                  for k, label, desc, origins in CATALOG],
        "contract": (
            "Toda sugestão carrega `origin`, `origin_label` e, quando existir, `source_name` e "
            "`source_date`. Sugestão sem origem é sugestão que a pessoa não pode avaliar — e por "
            "isso não existe neste produto."),
        "never_overwrites": (
            "A interface NUNCA substitui em silêncio o que a pessoa escreveu: o texto digitado é a "
            "verdade, e trocar por sugestão exige confirmação explícita."),
    }


def _row(value: str, label: str, *, sub: str | None = None, origin: str,
         source_name: str | None = None, source_date=None, verified: bool = False,
         extra: dict | None = None) -> dict:
    return {"value": value, "label": label, "sublabel": sub, "origin": origin,
            "origin_label": ORIGIN_LABEL[origin], "source_name": source_name,
            "source_date": source_date, "verified": verified, **(extra or {})}


def search(conn: Connection, *, key: str, q: str = "", limit: int = 10,
           org_id: str | None = None) -> dict:
    if key not in KEYS:
        raise unprocessable(f"Busca desconhecida: {key}.", code="unknown_lookup")
    term = (q or "").strip()
    # `%` e `_` digitados pela pessoa são TEXTO, não curinga: sem escapar, quem digita "%" recebe o
    # catálogo inteiro como se fosse sugestão para o que escreveu.
    like = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    items: list[dict] = []

    if key == "territories":
        for r in conn.query(
                "SELECT code, name, kind, parent_code, from_official_load, source_name,"
                " source_date FROM territories WHERE active"
                "   AND ($1 = '' OR name ILIKE $2 OR code ILIKE $2)"
                " ORDER BY kind, name LIMIT $3", term, like, limit):
            items.append(_row(
                r["code"], r["name"], sub=territory_sub(r), origin=(
                    "official_load" if r["from_official_load"] else "platform_knowledge"),
                source_name=r["source_name"], source_date=r["source_date"],
                verified=r["from_official_load"], extra={"kind": r["kind"]}))

    elif key == "ods":
        for r in conn.query(
                "SELECT number, name FROM ods_goals WHERE ($1 = '' OR name ILIKE $2"
                "   OR number::text = $1) ORDER BY number LIMIT $3", term, like, limit):
            items.append(_row(str(r["number"]), f"ODS {r['number']} — {r['name']}",
                              origin="platform_knowledge",
                              source_name="Agenda 2030 (nome e número; metas entram por carga)"))

    elif key == "ods_targets":
        for r in conn.query(
                "SELECT code, description, source FROM ods_targets"
                " WHERE ($1 = '' OR code ILIKE $2 OR description ILIKE $2)"
                " ORDER BY code LIMIT $3", term, like, limit):
            items.append(_row(r["code"], r["code"], sub=r["description"], origin="official_load",
                              source_name=r["source"], verified=True))

    elif key == "indicators":
        for r in conn.query(
                "SELECT id::text AS id, code, name, unit, esg_dimension, ods, origin, org_id"
                " FROM indicator_catalog WHERE active"
                "   AND ($1 = '' OR name ILIKE $2 OR code ILIKE $2)"
                "   AND (origin = 'platform' OR org_id = $4::uuid)"
                " ORDER BY origin, name LIMIT $3", term, like, limit, org_id):
            items.append(_row(
                r["id"], r["name"], sub=f"{r['code']} · {r['unit']}",
                origin=("platform_editorial" if r["origin"] == "platform"
                        else "your_organization"),
                extra={"code": r["code"], "unit": r["unit"], "ods": r["ods"],
                       "esg_dimension": r["esg_dimension"]}))

    elif key == "equity_barriers":
        for r in conn.query(
                "SELECT code, name_pt, dimension, source_note FROM equity_barrier_catalog"
                " WHERE active AND ($1 = '' OR name_pt ILIKE $2 OR code ILIKE $2)"
                " ORDER BY dimension, name_pt LIMIT $3", term, like, limit):
            items.append(_row(r["code"], r["name_pt"], sub=r["dimension"],
                              origin="platform_editorial", source_name=r["source_note"]))

    elif key == "determinants":
        for r in conn.query(
                "SELECT code, name_pt, determinant_code, unit, direction, usual_source"
                " FROM determinant_indicator_defs WHERE active"
                "   AND ($1 = '' OR name_pt ILIKE $2 OR code ILIKE $2)"
                " ORDER BY determinant_code, name_pt LIMIT $3", term, like, limit):
            items.append(_row(r["code"], r["name_pt"],
                              sub=f"{r['determinant_code']} · {r['unit']}",
                              origin="platform_editorial", source_name=r["usual_source"],
                              extra={"direction": r["direction"]}))

    elif key == "materiality_topics":
        for r in conn.query(
                "SELECT code, name_pt, pillar FROM materiality_topics WHERE active"
                "   AND ($1 = '' OR name_pt ILIKE $2 OR code ILIKE $2)"
                " ORDER BY pillar, name_pt LIMIT $3", term, like, limit):
            items.append(_row(r["code"], r["name_pt"], sub=f"pilar {r['pillar']}",
                              origin="platform_editorial",
                              extra={"pillar": r["pillar"]}))

    elif key == "frameworks":
        for r in conn.query(
                "SELECT key, name_pt, status, steward, official_url, reference_verified"
                " FROM impact_frameworks WHERE active"
                "   AND ($1 = '' OR name_pt ILIKE $2 OR key ILIKE $2)"
                " ORDER BY status, name_pt LIMIT $3", term, like, limit):
            items.append(_row(r["key"], r["name_pt"], sub=f"{r['status']} · {r['steward']}",
                              origin="platform_editorial", source_name=r["official_url"],
                              verified=r["reference_verified"],
                              extra={"status": r["status"]}))

    elif key == "seal_rules":
        for r in conn.query(
                "SELECT code, name_pt, scope FROM seal_rules"
                " WHERE ($1 = '' OR name_pt ILIKE $2 OR code ILIKE $2)"
                " ORDER BY scope, code LIMIT $3", term, like, limit):
            items.append(_row(r["code"], r["name_pt"], sub=r["scope"],
                              origin="platform_editorial"))

    elif key == "beneficiary_groups":
        for r in conn.query(
                "SELECT t.code, t.label_pt, x.usage_policy, x.source_name FROM taxonomy_terms t"
                " JOIN taxonomies x ON x.key = t.taxonomy"
                " WHERE t.taxonomy = 'beneficiary_group' AND t.active"
                "   AND ($1 = '' OR t.label_pt ILIKE $2 OR t.code ILIKE $2)"
                " ORDER BY t.position, t.label_pt LIMIT $3", term, like, limit):
            items.append(_row(r["code"], r["label_pt"], sub=r["usage_policy"],
                              origin="platform_editorial", source_name=r["source_name"]))

    elif key == "legal_natures":
        for r in conn.query(
                "SELECT code, label, source_citation, source_date FROM inst_catalog_items"
                " WHERE catalog = 'legal_nature' AND status = 'published'"
                "   AND ($1 = '' OR label ILIKE $2 OR code ILIKE $2)"
                " ORDER BY label LIMIT $3", term, like, limit):
            items.append(_row(r["code"], r["label"], origin="platform_editorial",
                              source_name=r["source_citation"], source_date=r["source_date"]))

    elif key == "my_suppliers":
        if not org_id:
            return {"items": [], "note": "Sem organização ativa: não há histórico para sugerir."}
        for r in conn.query(
                "SELECT supplier_name, supplier_cnpj, count(*) AS uses, max(paid_on) AS last_use"
                " FROM expenses WHERE org_id = $4::uuid AND supplier_name IS NOT NULL"
                "   AND ($1 = '' OR supplier_name ILIKE $2)"
                " GROUP BY supplier_name, supplier_cnpj ORDER BY max(paid_on) DESC LIMIT $3",
                term, like, limit, org_id):
            items.append(_row(r["supplier_name"], r["supplier_name"],
                              sub=f"{r['uses']} despesa(s); última em {r['last_use']}",
                              origin="your_organization",
                              extra={"supplier_cnpj": r["supplier_cnpj"]}))

    elif key == "my_projects":
        if not org_id:
            return {"items": [], "note": "Sem organização ativa: não há projeto para sugerir."}
        for r in conn.query(
                "SELECT id::text AS id, title, status, territory FROM projects"
                " WHERE org_id = $4::uuid AND ($1 = '' OR title ILIKE $2)"
                " ORDER BY created_at DESC LIMIT $3", term, like, limit, org_id):
            items.append(_row(r["id"], r["title"], sub=f"{r['status']} · {r['territory']}",
                              origin="your_organization", extra={"status": r["status"]}))

    return {"items": items, "key": key, "query": term,
            "note": ("Cada linha diz de onde veio. Nenhuma sugestão é aplicada sozinha: trocar o "
                     "que você escreveu exige confirmação.")}


def territory_sub(r: dict) -> str:
    base = {"country": "país", "region": "região", "state": "UF", "municipality": "município",
            "international": "internacional"}.get(r["kind"], r["kind"])
    return f"{base}{' · ' + r['parent_code'] if r.get('parent_code') else ''}"
