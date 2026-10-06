"""Interoperabilidade de frameworks e materialidade.

A PROMESSA DOS DOCUMENTOS E O QUE DELA É VERDADE HOJE

Os documentos vendem um "tradutor universal de impacto": executar uma vez e traduzir para ODS, ESG,
GRI, ISSB, IRIS+, SROI e outros. Este módulo entrega a estrutura dessa tradução **e diz quanto dela
ainda não existe**, porque a parte mais fácil de vender é a mais fácil de falsificar.

O registro classifica cada referencial em três estados honestos:

* `in_use` — a plataforma tem estrutura que o implementa, e o registro aponta qual. São quatro: ODS,
  ESG, Teoria da Mudança e Marco Lógico. Os dois últimos já funcionavam desde a v0.8.0 com outro
  nome: `impact_nodes` tem os sete tipos da cadeia e `impact_edges` tem a escada de ligação.
* `mappable` — dá para mapear indicador, e ninguém mapeou ainda.
* `registry_only` — reconhecido e **não mapeado**. GRI, ISSB, TCFD, TNFD, IRIS+, SROI, LCA e
  contabilidade de carbono estão aqui, com o motivo escrito em cada linha.

AS DUAS RECUSAS ESTRUTURAIS

1. **`certified` não existe.** A escada vai até `audited`. A plataforma não é organismo certificador,
   e o gatilho recusa a palavra com a razão — não com "valor viola restrição".
2. **Nenhum mapeamento para referencial de terceiro foi semeado.** Sem a lista oficial de códigos,
   mapear seria inventar, e alguém publicaria relatório citando código inexistente.

MATERIALIDADE

Dupla por padrão, e a lente é declarada (`impact_only`, `financial_only`, `double`) em vez de
subentendida. `is_material` é **derivada** do eixo e do limiar declarado na avaliação — não é
escrevível, e é por isso que a matriz não pode ser ajustada no fim para dar o resultado desejado.
"""
from __future__ import annotations

from ..db.pq import Connection, IntegrityError, InsufficientPrivilege
from ..http import ApiError, not_found, unprocessable

RELATIONS = ("aligned", "mapped", "assessed", "reported", "verified", "audited")
RELATION_LABEL = {
    "aligned": "alinhado — o indicador conversa com o referencial, sem conferência",
    "mapped": "mapeado — há correspondência declarada com um código do referencial",
    "assessed": "avaliado — alguém analisou a correspondência e registrou a análise",
    "reported": "relatado — o número foi publicado citando o referencial, com fonte",
    "verified": "verificado — conferido por revisor de OUTRA organização",
    "audited": "auditado — conferido por auditoria independente, com registro",
}
#: O degrau que não existe, e a razão. Fica declarado em código para que a API possa explicar.
REFUSED_RELATION = {
    "certified": ("A plataforma NÃO é organismo certificador. A escada vai até 'audited'. Chamar de "
                  "certificado o que não é certificação é a alegação que mais rápido destrói a "
                  "credibilidade de um relatório de impacto."),
}
LENSES = ("impact_only", "financial_only", "double")
LENS_LABEL = {
    "impact_only": "só impacto — quanto a organização afeta o mundo",
    "financial_only": "só financeira — quanto o tema afeta a organização",
    "double": "dupla materialidade — os dois eixos",
}


# ================================================================================================ registro
def registry(conn: Connection, *, status: str | None = None) -> dict:
    rows = conn.query(
        "SELECT key, name_pt, name_en, kind, steward, what_it_is, status, implemented_by,"
        " version_label, official_url, consulted_on, reference_verified, license_note"
        " FROM impact_frameworks WHERE active AND ($1::text IS NULL OR status = $1)"
        " ORDER BY CASE status WHEN 'in_use' THEN 0 WHEN 'mappable' THEN 1 ELSE 2 END, name_pt",
        status)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {
        "items": rows,
        "by_status": counts,
        "relations": [{"key": k, "label": RELATION_LABEL[k]} for k in RELATIONS],
        "refused_relations": [{"key": k, "reason": v} for k, v in REFUSED_RELATION.items()],
        "note": ("`in_use` significa que existe estrutura na plataforma implementando o referencial, "
                 "e `implemented_by` diz qual. `registry_only` significa reconhecido e NÃO mapeado — "
                 "o motivo está em `license_note` de cada um. Nenhuma linha tem "
                 "`reference_verified`: versão e URL oficiais precisam ser conferidas contra a fonte "
                 "por alguém, e o banco exige URL e data de consulta para marcar verdadeiro."),
    }


def mappings(conn: Connection, *, framework_key: str | None = None,
             indicator_id: str | None = None, org_id: str | None = None) -> dict:
    rows = conn.query(
        "SELECT m.id::text AS id, m.framework_key, f.name_pt AS framework_name, f.status AS"
        " framework_status, m.indicator_id::text AS indicator_id, i.code AS indicator_code,"
        " i.name AS indicator_name, m.external_code, m.external_name, m.relation, m.rationale,"
        " m.source_name, m.reviewed_at, m.org_id::text AS org_id, m.created_at"
        " FROM framework_mappings m"
        " JOIN impact_frameworks f ON f.key = m.framework_key"
        " JOIN indicator_catalog i ON i.id = m.indicator_id"
        " WHERE ($1::text IS NULL OR m.framework_key = $1)"
        "   AND ($2::uuid IS NULL OR m.indicator_id = $2)"
        "   AND ($3::uuid IS NULL OR m.org_id = $3)"
        " ORDER BY f.name_pt, i.name", framework_key, indicator_id, org_id)
    return {
        "items": [{**r, "relation_label": RELATION_LABEL[r["relation"]]} for r in rows],
        "note": ("Vazio é a resposta honesta enquanto ninguém mapear. A plataforma não semeia "
                 "mapeamento para referencial de terceiro: sem a lista oficial de códigos, o "
                 "mapeamento seria inventado."),
    }


def add_mapping(conn: Connection, *, framework_key: str, indicator_id: str, relation: str,
                rationale: str, org_id: str | None = None, external_code: str | None = None,
                external_name: str | None = None, source_name: str | None = None,
                reviewer_org_id: str | None = None, reviewer_user_id: str | None = None,
                actor: str | None = None) -> dict:
    if relation in REFUSED_RELATION:
        raise unprocessable(REFUSED_RELATION[relation], code="relation_refused")
    if relation not in RELATIONS:
        raise unprocessable(f"Relação desconhecida: {relation}", code="unknown_relation")
    if not conn.one("SELECT 1 FROM impact_frameworks WHERE key = $1 AND active", framework_key):
        raise not_found("Referencial não está no registro")
    if not conn.one("SELECT 1 FROM indicator_catalog WHERE id = $1 AND active", indicator_id):
        raise not_found("Indicador não encontrado no catálogo")
    try:
        row = conn.one(
            "INSERT INTO framework_mappings(framework_key, indicator_id, org_id, external_code,"
            " external_name, relation, rationale, source_name, reviewer_org_id, reviewer_user_id,"
            " reviewed_at, declared_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,"
            "         CASE WHEN $6 IN ('verified','audited') THEN now() END,$11)"
            " RETURNING id::text AS id, framework_key, relation, external_code, reviewed_at",
            framework_key, indicator_id, org_id, external_code, external_name, relation,
            rationale.strip(), source_name, reviewer_org_id, reviewer_user_id, actor)
    except (IntegrityError, InsufficientPrivilege) as exc:
        # A mensagem do gatilho é a parte útil (diz POR QUE a relação foi recusada). Gatilho que
        # levanta com ERRCODE 42501 virava 403 com texto genérico no tratador global — a mesma lição
        # que a v0.17.0 aprendeu com o portão de monetização.
        raise ApiError(422, "framework_gate", str(exc).split("\n")[0][:400]) from exc
    return {**row, "relation_label": RELATION_LABEL[row["relation"]]}


def remove_mapping(conn: Connection, *, mapping_id: str, org_id: str) -> dict:
    n = conn.run("DELETE FROM framework_mappings WHERE id = $1 AND org_id = $2", mapping_id, org_id)
    if not n:
        raise not_found("Mapeamento não encontrado")
    return {"removed": mapping_id}


def coverage(conn: Connection, *, org_id: str, framework_key: str) -> dict:
    """Responde "consigo relatar neste referencial?" com número, não com impressão."""
    fw = conn.one("SELECT key, name_pt, status, implemented_by, license_note"
                  " FROM impact_frameworks WHERE key = $1 AND active", framework_key)
    if not fw:
        raise not_found("Referencial não está no registro")
    nums = conn.one(
        "WITH used AS (SELECT DISTINCT pi.indicator_id FROM project_indicators pi"
        "               JOIN projects p ON p.id = pi.project_id WHERE p.org_id = $1)"
        " SELECT (SELECT count(*) FROM used) AS indicators_in_use,"
        " (SELECT count(*) FROM used u JOIN framework_mappings m ON m.indicator_id = u.indicator_id"
        "   AND m.framework_key = $2) AS mapped,"
        " (SELECT count(*) FROM used u JOIN framework_mappings m ON m.indicator_id = u.indicator_id"
        "   AND m.framework_key = $2 AND m.relation IN ('reported','verified','audited'))"
        "   AS reportable", org_id, framework_key)
    ready = fw["status"] != "registry_only" and (nums["mapped"] or 0) > 0
    return {
        "framework": fw,
        **nums,
        "can_report": bool(ready),
        "note": (("Este referencial está no registro como `registry_only`: a plataforma NÃO o mapeia, "
                  "então não há como relatar nele a partir daqui. O motivo está em `license_note`.")
                 if fw["status"] == "registry_only" else
                 ("Nenhum indicador da organização está mapeado para este referencial ainda."
                  if not nums["mapped"] else
                  "Relatar exige que o indicador esteja mapeado E que o número publicado cite a "
                  "fonte: a relação 'reported' para cima exige `source_name`.")),
    }


# ================================================================================================ materialidade
def topics(conn: Connection) -> dict:
    rows = conn.query(
        "SELECT t.code, t.name_pt, t.pillar, p.name_pt AS pillar_name, t.description, t.source_note"
        " FROM materiality_topics t JOIN esg_pillars p ON p.code = t.pillar"
        " WHERE t.active ORDER BY t.pillar, t.name_pt")
    return {
        "items": rows,
        "lenses": [{"key": k, "label": LENS_LABEL[k]} for k in LENSES],
        "note": ("Lista EDITORIAL da plataforma: não é a lista de temas de nenhum referencial "
                 "específico, e cada linha diz isso. A lente da avaliação é declarada, não "
                 "subentendida."),
    }


def open_assessment(conn: Connection, *, org_id: str, scope: str, period_label: str,
                    method_note: str, lens: str = "double", threshold: int = 4,
                    framework_key: str | None = None, program_id: str | None = None,
                    project_id: str | None = None, actor: str | None = None) -> dict:
    if lens not in LENSES:
        raise unprocessable(f"Lente desconhecida: {lens}", code="unknown_lens")
    row = conn.one(
        "INSERT INTO materiality_assessments(org_id, scope, program_id, project_id, period_label,"
        " framework_key, lens, threshold, method_note, created_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)"
        " RETURNING id::text AS id, scope, period_label, lens, threshold, status, created_at",
        org_id, scope, program_id, project_id, period_label.strip(), framework_key, lens,
        threshold, method_note.strip(), actor)
    return {**row, "lens_label": LENS_LABEL[row["lens"]]}


def set_entry(conn: Connection, *, assessment_id: str, org_id: str, topic_code: str,
              rationale: str, impact_score: int | None = None,
              financial_score: int | None = None, stakeholder_note: str | None = None,
              evidence_id: str | None = None, indicator_id: str | None = None) -> dict:
    owner = conn.scalar("SELECT org_id::text FROM materiality_assessments WHERE id = $1",
                        assessment_id)
    if not owner:
        raise not_found("Avaliação de materialidade não encontrada")
    if owner != org_id:
        raise ApiError(403, "forbidden", "A avaliação é da organização que a abriu.")
    try:
        row = conn.one(
            "INSERT INTO materiality_entries(assessment_id, topic_code, impact_score,"
            " financial_score, rationale, stakeholder_note, evidence_id, indicator_id)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8)"
            " ON CONFLICT (assessment_id, topic_code) DO UPDATE SET"
            " impact_score = excluded.impact_score, financial_score = excluded.financial_score,"
            " rationale = excluded.rationale, stakeholder_note = excluded.stakeholder_note,"
            " evidence_id = excluded.evidence_id, indicator_id = excluded.indicator_id"
            " RETURNING id::text AS id, topic_code, impact_score, financial_score, is_material",
            assessment_id, topic_code, impact_score, financial_score, rationale.strip(),
            stakeholder_note, evidence_id, indicator_id)
    except (IntegrityError, InsufficientPrivilege) as exc:
        raise ApiError(422, "materiality_rule", str(exc).split("\n")[0][:400]) from exc
    return row


def publish(conn: Connection, *, assessment_id: str, org_id: str) -> dict:
    try:
        row = conn.one(
            "UPDATE materiality_assessments SET status = 'published'"
            " WHERE id = $1 AND org_id = $2 AND status = 'draft'"
            " RETURNING id::text AS id, status, published_at", assessment_id, org_id)
    except (IntegrityError, InsufficientPrivilege) as exc:
        raise ApiError(422, "materiality_rule", str(exc).split("\n")[0][:400]) from exc
    if not row:
        raise unprocessable("Só rascunho da própria organização pode ser publicado.",
                            code="not_publishable")
    return row


def assessment(conn: Connection, *, assessment_id: str) -> dict:
    head = conn.one(
        "SELECT id::text AS id, org_id::text AS org_id, scope, program_id::text AS program_id,"
        " project_id::text AS project_id, period_label, framework_key, lens, threshold,"
        " method_note, status, published_at, created_at"
        " FROM materiality_assessments WHERE id = $1", assessment_id)
    if not head:
        raise not_found("Avaliação de materialidade não encontrada")
    rows = conn.query(
        "SELECT topic_code, name_pt, pillar, impact_score, financial_score, is_material, rationale,"
        " has_evidence, has_indicator FROM materiality_matrix($1)", assessment_id)
    material = [r for r in rows if r["is_material"]]
    return {
        **head,
        "lens_label": LENS_LABEL[head["lens"]],
        "matrix": rows,
        "material_count": len(material),
        "topics_assessed": len(rows),
        "note": ("`is_material` é DERIVADA do eixo e do limiar declarado nesta avaliação — não é "
                 "escrevível. É isso que impede ajustar a matriz no fim para dar o resultado "
                 "desejado. Tema avaliado sem evidência e sem indicador vinculado aparece com "
                 "`has_evidence` e `has_indicator` falsos, de propósito."),
    }


def assessments(conn: Connection, *, org_id: str, limit: int = 20) -> dict:
    return {"items": conn.query(
        "SELECT a.id::text AS id, a.scope, a.period_label, a.lens, a.threshold, a.status,"
        " a.published_at, a.created_at,"
        " (SELECT count(*) FROM materiality_entries e WHERE e.assessment_id = a.id) AS topics,"
        " (SELECT count(*) FROM materiality_entries e WHERE e.assessment_id = a.id AND e.is_material)"
        "   AS material FROM materiality_assessments a"
        " WHERE a.org_id = $1 ORDER BY a.created_at DESC LIMIT $2", org_id, limit)}
