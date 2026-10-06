"""Responsabilidade: quem responde por quê, em que escopo, em que período — e por qual decisão.

Separado de assinatura de propósito. Assinatura (v0.14.0) amarra uma PESSOA a um CONTEÚDO e responde
"quem conferiu este texto exato". Responsabilidade responde "quem responde por esta decisão, em que
papel e em que período". Misturar as duas produz os dois erros clássicos: documento assinado por
quem não tinha competência para decidir, e decisão tomada por quem tinha competência mas sem
registro nenhum.

As travas moram no banco (migração 0031): designação não é reescrita, um papel por escopo tem um
responsável corrente, encerrar exige motivo, decisão fora do período é recusada, decisão sobre
documento é sobre uma VERSÃO, e quatro-olhos é declarado em dado (`requires_two`) e aplicado por
gatilho.
"""
from __future__ import annotations

from ..db.pq import Connection, IntegrityError, InsufficientPrivilege
from ..http import ApiError, not_found, unprocessable

SCOPE_TABLE = {
    "organization": ("organizations", "id"),
    "program": ("programs", "owner_org_id"),
    "project": ("projects", "org_id"),
    "document": ("documents", "org_id"),
}

SEPARATION_NOTE = (
    "Responsabilidade NÃO é assinatura. Esta designação registra quem responde por um escopo num "
    "período; assinatura registra quem conferiu um conteúdo exato (sha256). Uma decisão pode "
    "existir sem assinatura, e uma assinatura pode existir sem decisão."
)


def roles(conn: Connection) -> dict:
    return {
        "items": conn.query(
            "SELECT code, name_pt, answers_for, does_not_answer_for, scopes FROM"
            " responsibility_roles WHERE active ORDER BY position"),
        "decision_kinds": conn.query(
            "SELECT code, name_pt, what_it_is, requires_two FROM responsibility_decision_kinds"
            " WHERE active ORDER BY code"),
        "note": ("Lista editorial: a redação é nossa. Papel formal exigido por lei (dirigente, "
                 "contador) continua sendo o que o estatuto e o contrato dizem — designar aqui "
                 "NÃO cria poder de representação."),
        "separation": SEPARATION_NOTE,
    }


def _assert_subject(conn: Connection, *, scope: str, subject_id: str, org_id: str) -> None:
    table, owner = SCOPE_TABLE[scope]
    row = conn.one(f"SELECT {owner}::text AS owner FROM {table} WHERE id = $1", subject_id)  # noqa: S608
    if not row:
        raise ApiError(404, "not_found", "Sujeito da designação não encontrado.")
    if row["owner"] != org_id:
        raise ApiError(403, "forbidden",
                       "A designação é feita por quem é dono do escopo designado.")


def assign(conn: Connection, *, org_id: str, scope: str, subject_id: str, role_code: str,
           mandate_basis: str, user_id: str | None = None, external_name: str | None = None,
           external_note: str | None = None, starts_on=None, actor: str | None = None) -> dict:
    if (user_id is None) == (external_name is None):
        raise unprocessable(
            "Informe a pessoa da plataforma OU o nome da pessoa externa — e apenas um dos dois.",
            code="person_required")
    _assert_subject(conn, scope=scope, subject_id=subject_id, org_id=org_id)
    if user_id and not conn.one(
            "SELECT 1 FROM memberships WHERE user_id = $1 AND org_id = $2", user_id, org_id):
        raise unprocessable(
            "A pessoa designada precisa ser membro ativo da organização. Pessoa de fora entra "
            "como pessoa externa, pelo nome.", code="not_a_member")
    try:
        row = conn.one(
            "INSERT INTO responsibility_assignments(org_id, role_code, scope, subject_id, user_id,"
            " external_name, external_note, mandate_basis, starts_on, assigned_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,coalesce($9::date, current_date),$10)"
            " RETURNING id::text AS id, role_code, scope, subject_id::text AS subject_id,"
            " starts_on",
            org_id, role_code, scope, subject_id, user_id, external_name, external_note,
            mandate_basis.strip(), starts_on, actor)
    except (IntegrityError, InsufficientPrivilege) as exc:
        msg = str(exc).split("\n")[0]
        if "ux_responsibility_current" in str(exc):
            raise ApiError(409, "role_already_held",
                           "Este papel já tem responsável corrente neste escopo. Encerre a "
                           "designação atual (com motivo) antes de designar outra pessoa.") from exc
        raise ApiError(422, "assignment_refused", msg[:400]) from exc
    return {**row, "separation": SEPARATION_NOTE}


def end(conn: Connection, *, assignment_id: str, org_id: str, reason: str, ended_on=None) -> dict:
    row = conn.one(
        "UPDATE responsibility_assignments SET ended_on = coalesce($4::date, current_date),"
        " ended_reason = $3 WHERE id = $1 AND org_id = $2 AND ended_on IS NULL"
        " RETURNING id::text AS id, role_code, ended_on, ended_reason",
        assignment_id, org_id, reason.strip(), ended_on)
    if not row:
        raise unprocessable("Designação não encontrada ou já encerrada.", code="not_endable")
    return {**row,
            "note": ("A designação encerrada CONTINUA legível, com o período: é assim que se sabe "
                     "quem respondia no dia do fato.")}


def current(conn: Connection, *, scope: str, subject_id: str) -> dict:
    rows = conn.query(
        "SELECT role_code, role_name, assignment_id::text AS assignment_id, who, kind, starts_on,"
        " mandate_basis FROM responsible_now($1, $2)", scope, subject_id)
    faltando = conn.query(
        "SELECT code, name_pt, answers_for FROM responsibility_roles"
        " WHERE active AND $1 = ANY (scopes)"
        "   AND code NOT IN (SELECT role_code FROM responsibility_assignments"
        "                     WHERE scope = $1 AND subject_id = $2 AND ended_on IS NULL)"
        " ORDER BY position", scope, subject_id)
    return {"scope": scope, "subject_id": subject_id, "items": rows,
            "without_responsible": faltando,
            "note": ("Os papéis sem responsável aparecem à parte, de propósito: ausência de "
                     "responsável é informação, e não um espaço em branco na tela."),
            "separation": SEPARATION_NOTE}


def history(conn: Connection, *, scope: str, subject_id: str, org_id: str) -> dict:
    rows = conn.query(
        "SELECT a.id::text AS id, a.role_code, r.name_pt AS role_name,"
        " coalesce(u.full_name, a.external_name) AS who,"
        " CASE WHEN a.user_id IS NOT NULL THEN 'platform_user' ELSE 'external_person' END AS kind,"
        " a.mandate_basis, a.starts_on, a.ended_on, a.ended_reason, a.created_at,"
        " (SELECT count(*) FROM responsibility_decisions d WHERE d.assignment_id = a.id)"
        "   AS decisions"
        " FROM responsibility_assignments a"
        " JOIN responsibility_roles r ON r.code = a.role_code"
        " LEFT JOIN users u ON u.id = a.user_id"
        " WHERE a.scope = $1 AND a.subject_id = $2 AND (a.org_id = $3::uuid OR $3::uuid IS NULL)"
        " ORDER BY a.starts_on DESC, r.position", scope, subject_id, org_id)
    return {"items": rows}


def mine(conn: Connection, *, user_id: str) -> dict:
    rows = conn.query(
        "SELECT a.id::text AS id, a.role_code, r.name_pt AS role_name, a.scope,"
        " a.subject_id::text AS subject_id, a.starts_on, a.ended_on, a.mandate_basis"
        " FROM responsibility_assignments a JOIN responsibility_roles r ON r.code = a.role_code"
        " WHERE a.user_id = $1 ORDER BY a.ended_on NULLS FIRST, a.starts_on DESC LIMIT 200",
        user_id)
    return {"items": rows,
            "note": ("O que você responde hoje e o que respondeu antes. Encerrada não desaparece: "
                     "responsabilidade passada é fato.")}


# ================================================================================================ decisão
def decide(conn: Connection, *, assignment_id: str, org_id: str, kind: str, statement: str,
           document_id: str | None = None, document_version: int | None = None,
           signature_id: str | None = None, second_assignment_id: str | None = None,
           second_statement: str | None = None, taken_on=None) -> dict:
    a = conn.one("SELECT org_id::text AS org_id FROM responsibility_assignments WHERE id = $1",
                 assignment_id)
    if not a:
        raise not_found("Designação")
    if a["org_id"] != org_id:
        raise ApiError(403, "forbidden", "A decisão é registrada pela organização da designação.")
    try:
        row = conn.one(
            "INSERT INTO responsibility_decisions(assignment_id, kind, statement, document_id,"
            " document_version, signature_id, second_assignment_id, second_statement, taken_on)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,coalesce($9::date, current_date))"
            " RETURNING id::text AS id, kind, taken_on",
            assignment_id, kind, statement.strip(), document_id, document_version, signature_id,
            second_assignment_id, (second_statement.strip() if second_statement else None),
            taken_on)
    except (IntegrityError, InsufficientPrivilege) as exc:
        raise ApiError(422, "decision_refused", str(exc).split("\n")[0][:500]) from exc
    return {**row, "signed": signature_id is not None, "separation": SEPARATION_NOTE}


def decisions(conn: Connection, *, scope: str | None = None, subject_id: str | None = None,
              assignment_id: str | None = None, limit: int = 100) -> dict:
    rows = conn.query(
        "SELECT d.id::text AS id, d.kind, k.name_pt AS kind_name, k.requires_two, d.statement,"
        " d.document_id::text AS document_id, d.document_version,"
        " d.signature_id::text AS signature_id, d.taken_on, d.second_statement,"
        " a.role_code, r.name_pt AS role_name, a.scope, a.subject_id::text AS subject_id,"
        " coalesce(u.full_name, a.external_name) AS who,"
        " coalesce(u2.full_name, b.external_name) AS second_who"
        " FROM responsibility_decisions d"
        " JOIN responsibility_decision_kinds k ON k.code = d.kind"
        " JOIN responsibility_assignments a ON a.id = d.assignment_id"
        " JOIN responsibility_roles r ON r.code = a.role_code"
        " LEFT JOIN users u ON u.id = a.user_id"
        " LEFT JOIN responsibility_assignments b ON b.id = d.second_assignment_id"
        " LEFT JOIN users u2 ON u2.id = b.user_id"
        " WHERE ($1::text IS NULL OR a.scope = $1) AND ($2::uuid IS NULL OR a.subject_id = $2)"
        "   AND ($3::uuid IS NULL OR d.assignment_id = $3)"
        " ORDER BY d.taken_on DESC, d.created_at DESC LIMIT $4",
        scope, subject_id, assignment_id, limit)
    return {"items": [{**r, "signed": r["signature_id"] is not None} for r in rows],
            "separation": SEPARATION_NOTE}
