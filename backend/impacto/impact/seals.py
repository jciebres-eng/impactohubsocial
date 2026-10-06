"""Motor de selos: definição versionada, critério avaliado em SQL, selo nunca comprável.

A decisão que torna o selo infalsificável está no banco, não aqui: `seal_evaluate()` consulta os
fatos e `app_award_seal()` recusa conceder quando algum critério não está satisfeito. Este módulo
não decide nada — ele pergunta ao banco e traduz a resposta.

Consequência prática: a aplicação **não tem INSERT** em `seal_awards`. Não existe rota, correção
manual ou job capaz de conceder selo sem que o banco concorde.

Nenhum critério é comercial e nenhum critério é reputação: encadear selo em nota transformaria a
nota naquilo que a FASE 6 recusou ser.
"""
from __future__ import annotations

import json

from ..db.pq import Connection, IntegrityError, InsufficientPrivilege
from ..http import ApiError, not_found, unprocessable

ENGINE_VERSION = "seal-rules@1.0.0"

SEAL_DISCLAIMER = (
    "Selo da plataforma, calculado por regra a partir de fatos registrados. NÃO é certificação, "
    "homologação nem aprovação de órgão público, não garante elegibilidade em edital e não pode ser "
    "comprado: não existe caminho de pagamento que conceda selo, e o critério é avaliado no banco."
)
STATUS_LABEL = {
    "active": "ativo",
    "expired": "expirado",
    "revoked": "revogado",
    "superseded_definition": "definição superada por versão nova",
    "definition_retired": "definição aposentada",
}
REVOCATION_LABEL = {
    "criterion_no_longer_met": "critério deixou de ser satisfeito",
    "definition_retired": "definição aposentada",
    "data_correction": "correção de dado",
    "request_of_holder": "pedido de quem recebeu",
    "misconduct": "conduta",
}


# ================================================================================================ catálogo
def rules(conn: Connection) -> dict:
    return {
        "items": conn.query(
            "SELECT code, scope, name_pt, what_it_checks, params_note FROM seal_rules"
            " ORDER BY scope, code"),
        "note": ("Conjunto FECHADO: cada código tem implementação em `seal_evaluate()` (SQL). "
                 "Regra nova exige migração — critério de selo não deveria poder nascer de um "
                 "INSERT."),
        "disclaimer": SEAL_DISCLAIMER,
    }


def definitions(conn: Connection, *, scope: str | None = None, code: str | None = None,
                status: str | None = None) -> dict:
    rows = conn.query(
        "SELECT id::text AS id, code, version, scope, title, what_it_attests,"
        " what_it_does_not_attest, validity_days, status, published_at, retired_at"
        " FROM seal_definitions WHERE ($1::text IS NULL OR scope = $1)"
        "   AND ($2::text IS NULL OR code = $2) AND ($3::text IS NULL OR status = $3)"
        " ORDER BY code, version DESC", scope, code, status)
    for r in rows:
        r["criteria"] = conn.query(
            "SELECT c.rule_code, c.params, r.name_pt, r.what_it_checks FROM seal_criteria c"
            " JOIN seal_rules r ON r.code = c.rule_code WHERE c.definition_id = $1"
            " ORDER BY c.position", r["id"])
    return {
        "items": rows, "disclaimer": SEAL_DISCLAIMER,
        "note": ("Nenhuma definição nasce publicada, e esta plataforma não embarca nenhuma: "
                 "critério de selo é decisão de produto, e inventá-la numa migração seria a mesma "
                 "coisa que inventar regra fiscal. Rascunho é legível de propósito, para que "
                 "ninguém seja pego de surpresa por critério novo."),
    }


# ================================================================================================ definição
def create_definition(conn: Connection, *, code: str, scope: str, title: str,
                      what_it_attests: str, what_it_does_not_attest: str, validity_days: int,
                      criteria: list[dict]) -> dict:
    if not criteria:
        raise unprocessable("Definição sem critério não existe: selo é regra.",
                            code="criteria_required")
    known = {r["code"]: r["scope"] for r in conn.query("SELECT code, scope FROM seal_rules")}
    for c in criteria:
        if c["rule_code"] not in known:
            raise unprocessable(f"Critério desconhecido: {c['rule_code']}.", code="unknown_rule")
        if known[c["rule_code"]] != scope:
            raise unprocessable(
                f"O critério {c['rule_code']} é de escopo {known[c['rule_code']]}, e esta "
                f"definição é de escopo {scope}.", code="scope_mismatch")
    version = (conn.scalar("SELECT coalesce(max(version), 0) FROM seal_definitions WHERE code = $1",
                           code) or 0) + 1
    row = conn.one(
        "INSERT INTO seal_definitions(code, version, scope, title, what_it_attests,"
        " what_it_does_not_attest, validity_days) VALUES ($1,$2,$3,$4,$5,$6,$7)"
        " RETURNING id::text AS id, code, version, status",
        code, version, scope, title.strip(), what_it_attests.strip(),
        what_it_does_not_attest.strip(), validity_days)
    for i, c in enumerate(criteria):
        conn.run("INSERT INTO seal_criteria(definition_id, rule_code, params, position)"
                 " VALUES ($1,$2,$3::jsonb,$4)", row["id"], c["rule_code"],
                 json.dumps(c.get("params") or {}), i)
    return {**row, "criteria": len(criteria),
            "note": "Nasce RASCUNHO: rascunho não concede selo nenhum."}


def publish_definition(conn: Connection, *, definition_id: str) -> dict:
    d = conn.one("SELECT code, version, status FROM seal_definitions WHERE id = $1", definition_id)
    if not d:
        raise not_found("Definição de selo")
    if d["status"] != "draft":
        raise unprocessable("Só rascunho é publicado; definição publicada é imutável.",
                            code="not_draft")
    if not conn.scalar("SELECT count(*) FROM seal_criteria WHERE definition_id = $1", definition_id):
        raise unprocessable("Definição sem critério não é publicada.", code="criteria_required")
    # Publicar a versão nova APOSENTA a anterior: só existe uma definição corrente por código, e as
    # concessões da anterior passam a aparecer como "definição superada" — não deixam de existir.
    retired = conn.query(
        "UPDATE seal_definitions SET status = 'retired', retired_at = now()"
        " WHERE code = $1 AND status = 'published' RETURNING id::text AS id, version", d["code"])
    row = conn.one(
        "UPDATE seal_definitions SET status = 'published', published_at = now()"
        " WHERE id = $1 RETURNING id::text AS id, code, version, status, published_at",
        definition_id)
    return {**row, "retired_versions": [r["version"] for r in retired],
            "note": ("As concessões da versão anterior continuam legíveis, com situação "
                     "`superseded_definition`: selo concedido sob outro critério não é apagado "
                     "nem silenciosamente convertido.")}


def retire_definition(conn: Connection, *, definition_id: str) -> dict:
    row = conn.one(
        "UPDATE seal_definitions SET status = 'retired', retired_at = now()"
        " WHERE id = $1 AND status = 'published'"
        " RETURNING id::text AS id, code, version, retired_at", definition_id)
    if not row:
        raise unprocessable("Só definição publicada é aposentada.", code="not_published")
    return {**row, "note": "Aposentar não revoga as concessões: elas passam a aparecer como de "
                           "definição aposentada, com a data em que isso aconteceu."}


# ================================================================================================ avaliação
def evaluate(conn: Connection, *, definition_id: str, subject_id: str) -> dict:
    d = conn.one("SELECT code, version, scope, status, title FROM seal_definitions WHERE id = $1",
                 definition_id)
    if not d:
        raise not_found("Definição de selo")
    try:
        rows = conn.query(
            "SELECT rule_code, met, detail, expires_on FROM seal_evaluate($1, $2)",
            definition_id, subject_id)
    except (IntegrityError, InsufficientPrivilege) as exc:
        raise ApiError(422, "seal_evaluation_failed", str(exc).split("\n")[0][:400]) from exc
    unmet = [r for r in rows if not r["met"]]
    return {"definition": d, "criteria": rows, "all_met": not unmet,
            "unmet": [r["rule_code"] for r in unmet], "engine_version": ENGINE_VERSION,
            "disclaimer": SEAL_DISCLAIMER,
            "note": ("Esta é a MESMA avaliação que a concessão usa: ela roda no banco, e a "
                     "concessão a repete antes de inserir. Não existe divergência possível entre o "
                     "que esta rota mostra e o que o selo exige.")}


def award(conn: Connection, *, definition_id: str, subject_id: str) -> dict:
    """Concede, ou devolve a recusa SEM levantar exceção.

    A recusa não levanta exceção aqui porque isso desfaria a transação e levaria embora o registro
    da avaliação — o registro que responde "por que eu não recebi". Quem chama transforma
    `awarded: False` em 422 **depois** do COMMIT.
    """
    try:
        award_id = conn.scalar("SELECT app_award_seal($1, $2, $3)", definition_id, subject_id,
                               ENGINE_VERSION)
    except (IntegrityError, InsufficientPrivilege) as exc:
        # Erro estrutural (definição em rascunho, sujeito inexistente): não é avaliação.
        raise ApiError(422, "seal_not_awardable", str(exc).split("\n")[0][:600]) from exc
    if award_id is None:
        last = conn.one(
            "SELECT id, detail FROM seal_evaluations WHERE definition_id = $1 AND subject_id = $2"
            " ORDER BY created_at DESC LIMIT 1", definition_id, subject_id)
        unmet = [d for d in (last["detail"] if last else []) if not d.get("met")]
        return {"awarded": False, "evaluation_id": last["id"] if last else None,
                "unmet": unmet,
                "message": "Critério(s) não satisfeito(s): "
                           + "; ".join(f"{d['rule_code']} ({d['detail']})" for d in unmet),
                "note": ("A avaliação que não concedeu ficou REGISTRADA e é legível pela "
                         "organização em /v1/seals/evaluations.")}
    return {"awarded": True, **get(conn, award_id=award_id),
            "note": ("A concessão reavaliou os critérios NO BANCO antes de existir. Se algum "
                     "deixar de valer, a revogação é um fato novo — o selo não é apagado.")}


# ================================================================================================ concessões
def get(conn: Connection, *, award_id: str) -> dict:
    a = conn.one(
        "SELECT a.id::text AS id, a.scope, a.subject_id::text AS subject_id,"
        " a.org_id::text AS org_id, a.evidence, a.expires_on, a.engine_version, a.awarded_at,"
        " d.code, d.version, d.title, d.what_it_attests, d.what_it_does_not_attest,"
        " d.id::text AS definition_id, s.status, s.revoked_at, s.revocation_reason"
        " FROM seal_awards a JOIN seal_definitions d ON d.id = a.definition_id"
        " CROSS JOIN LATERAL seal_status(a.id) s WHERE a.id = $1", award_id)
    if not a:
        raise not_found("Selo")
    rev = conn.one("SELECT reason, detail, revoked_at FROM seal_revocations WHERE award_id = $1",
                   award_id)
    return {**a, "status_label": STATUS_LABEL.get(a["status"], a["status"]),
            "revocation": ({**rev, "reason_label": REVOCATION_LABEL.get(rev["reason"],
                                                                        rev["reason"])}
                           if rev else None),
            "disclaimer": SEAL_DISCLAIMER}


def awards(conn: Connection, *, scope: str | None = None, subject_id: str | None = None,
           org_id: str | None = None, active_only: bool = False) -> dict:
    rows = conn.query(
        "SELECT a.id::text AS id, a.scope, a.subject_id::text AS subject_id, a.expires_on,"
        " a.awarded_at, d.code, d.version, d.title, s.status, s.revoked_at"
        " FROM seal_awards a JOIN seal_definitions d ON d.id = a.definition_id"
        " CROSS JOIN LATERAL seal_status(a.id) s"
        " WHERE ($1::text IS NULL OR a.scope = $1) AND ($2::uuid IS NULL OR a.subject_id = $2)"
        "   AND ($3::uuid IS NULL OR a.org_id = $3)"
        "   AND (NOT $4::boolean OR s.status = 'active')"
        " ORDER BY a.awarded_at DESC LIMIT 200", scope, subject_id, org_id, active_only)
    return {"items": [{**r, "status_label": STATUS_LABEL.get(r["status"], r["status"])}
                      for r in rows],
            "disclaimer": SEAL_DISCLAIMER}


def revoke(conn: Connection, *, award_id: str, reason: str, detail: str,
           actor: str | None = None) -> dict:
    if not conn.one("SELECT 1 FROM seal_awards WHERE id = $1", award_id):
        raise not_found("Selo")
    if conn.one("SELECT 1 FROM seal_revocations WHERE award_id = $1", award_id):
        raise unprocessable("Este selo já está revogado, e a revogação é append-only.",
                            code="already_revoked")
    conn.run("INSERT INTO seal_revocations(award_id, reason, detail, revoked_by)"
             " VALUES ($1,$2,$3,$4)", award_id, reason, detail.strip(), actor)
    return get(conn, award_id=award_id)


def evaluations(conn: Connection, *, org_id: str, limit: int = 50) -> dict:
    rows = conn.query(
        "SELECT e.id, e.scope, e.subject_id::text AS subject_id, e.all_met, e.detail,"
        " e.engine_version, e.created_at, d.code, d.version, d.title"
        " FROM seal_evaluations e JOIN seal_definitions d ON d.id = e.definition_id"
        " WHERE e.org_id = $1 ORDER BY e.created_at DESC LIMIT $2", org_id, limit)
    return {"items": rows,
            "note": ("A avaliação que NÃO concedeu também está aqui, com o critério que faltou: "
                     "'por que eu não recebi' é a pergunta mais legítima que existe sobre um "
                     "selo.")}


def recheck(conn: Connection, *, org_id: str | None = None) -> dict:
    """Reavalia selos ativos e REVOGA os que deixaram de satisfazer o critério.

    Selo que continua aparecendo depois de o critério cair é pior que não ter selo: atesta o que
    não é mais verdade. A revogação diz `criterion_no_longer_met` e cita o critério.
    """
    rows = conn.query(
        "SELECT a.id::text AS id, a.definition_id::text AS definition_id,"
        " a.subject_id::text AS subject_id FROM seal_awards a"
        " CROSS JOIN LATERAL seal_status(a.id) s"
        " WHERE s.status = 'active' AND ($1::uuid IS NULL OR a.org_id = $1)"
        " ORDER BY a.awarded_at LIMIT 500", org_id)
    revoked = []
    for a in rows:
        unmet = conn.query(
            "SELECT rule_code, detail FROM seal_evaluate($1, $2) WHERE NOT met",
            a["definition_id"], a["subject_id"])
        if not unmet:
            continue
        conn.run("INSERT INTO seal_revocations(award_id, reason, detail)"
                 " VALUES ($1, 'criterion_no_longer_met', $2)", a["id"],
                 "Critério(s) que deixaram de ser satisfeitos: "
                 + "; ".join(f"{u['rule_code']} ({u['detail']})" for u in unmet)[:1900])
        revoked.append(a["id"])
    return {"checked": len(rows), "revoked": len(revoked), "revoked_ids": revoked}
