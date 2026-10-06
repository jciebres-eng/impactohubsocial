"""Documento legal versionado e aceite com prova.

O QUE ESTA CAMADA RESOLVE

"O usuário aceitou os termos" só é afirmação verificável se houver: qual documento, qual versão, qual
texto (por hash), quem aceitou, quando e de onde. Sem isso é lembrança, não prova.

O ESTADO REAL, HOJE

As onze minutas registradas foram escritas a partir do funcionamento do software — não de modelo de
contrato — e **nenhuma passou por advogado(a)**. Logo nenhuma está aprovada, nenhuma está vigente e
**nenhuma pode ser aceita**: o gatilho `acceptance_stamp()` recusa aceite de documento que não esteja
aprovado e vigente. `pending()` devolve lista vazia para todo mundo, e isso é o estado verdadeiro.

A consequência prática é desconfortável de propósito: o produto não consegue coletar aceite enquanto o
proprietário não contratar a revisão jurídica. Era isso ou coletar aceite de rascunho, que é pior.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, IntegrityError
from ..http import ApiError

#: Apelidos antigos da rota pública `/v1/legal/{doc}` (v0.7.0) para as chaves do registro.
ALIASES = {"termos": "terms_of_use", "privacidade": "privacy_policy", "cookies": "cookies",
           "assinatura": "subscription", "marketplace": "marketplace",
           "intermediacao": "intermediation", "pagamento": "payment",
           "cancelamento": "cancellation", "reembolso": "refund", "b2b": "b2b", "b2g": "b2g"}

STATUS_LABEL = {
    "draft": "MINUTA — DRAFT FOR LEGAL REVIEW",
    "in_legal_review": "em revisão jurídica",
    "approved": "aprovado e vigente",
    "superseded": "superado por versão nova",
}


def overview(conn: Connection) -> dict:
    rows = conn.query("SELECT * FROM legal_overview()")
    blocking = [r["doc_key"] for r in rows if r["blocks_product"]]
    approved = [r["doc_key"] for r in rows if r["status"] == "approved"]
    return {
        "items": [{**r, "status_label": STATUS_LABEL.get(r["status"], r["status"])} for r in rows],
        "documents": len(rows),
        "approved": len(approved),
        "drafts": len(rows) - len(approved),
        "blocking_product": blocking,
        "can_collect_acceptance": bool(approved),
        "note": ("Documento que exige aceite e não está aprovado aparece em `blocking_product`: o "
                 "produto não pode exigir aceite dele. Enquanto houver documento nessa lista, o "
                 "lançamento tem pendência jurídica — não técnica."),
    }


def text(conn: Connection, *, key: str) -> dict:
    row = conn.one("SELECT * FROM legal_text($1)", ALIASES.get(key, key))
    if not row:
        raise ApiError(404, "not_found", "Documento legal não encontrado")
    return {**row, "status_label": STATUS_LABEL.get(row["status"], row["status"])}


def pending(conn: Connection, *, user_id: str, org_kind: str | None) -> dict:
    rows = conn.query("SELECT * FROM legal_pending($1, $2)", user_id, org_kind or "all")
    return {
        "items": rows,
        "note": ("Vazio significa que não há documento APROVADO E VIGENTE exigindo aceite. Hoje é o "
                 "caso de todos: as onze são minutas. Não significa que o usuário já aceitou."),
    }


def blockers(conn: Connection) -> list[dict]:
    """Documentos que EXIGEM aceite e não estão aprovados — a pendência jurídica do lançamento.

    Enquanto esta lista não estiver vazia, o produto não pode coletar aceite válido: o gatilho do
    banco recusa aceite de minuta, e a caixa "Li e aceito" na tela de cadastro estaria coletando
    concordância com um texto que ninguém aprovou e do qual não ficaria prova nenhuma.
    """
    return [{"doc_key": r["doc_key"], "title": r["title"], "version": r["latest_version"],
             "status": r["status"], "status_label": STATUS_LABEL.get(r["status"], r["status"])}
            for r in conn.query("SELECT * FROM legal_overview()") if r["blocks_product"]]


def accept_on_signup(conn: Connection, *, user_id: str, org_id: str | None, audience: str | None,
                     ip: str | None, user_agent: str | None) -> list[dict]:
    """Registra, no cadastro, o aceite de TODO documento vigente que exige aceite.

    POR QUE ISTO EXISTE. Até a v0.20.0 a tela de cadastro mostrava "Li e aceito os Termos de uso e a
    Política de privacidade", o cadastro conferia um booleano e gravava `consents` com uma string de
    versão vinda do arquivo de configuração. A prova de verdade — documento, versão e **hash do
    texto** — mora em `legal_acceptances`, e o cadastro nunca escrevia lá. Resultado: em produção
    cada pessoa aceitaria um texto sem que sobrasse prova de QUAL texto foi aceito.

    Devolve a lista do que foi aceito. Lista vazia significa que não há documento vigente exigindo
    aceite — o que hoje é verdade e é tratado por `blockers()`, não escondido aqui.
    """
    aceitos = []
    for doc in conn.query("SELECT * FROM legal_pending($1, $2)", user_id, audience or "all"):
        row = conn.one(
            "INSERT INTO legal_acceptances(document_id, user_id, org_id, ip, user_agent, source)"
            " VALUES ($1,$2,$3,$4,$5,'signup')"
            " ON CONFLICT (document_id, user_id) DO NOTHING"
            " RETURNING doc_key, version, body_sha256, accepted_at",
            doc["id"], user_id, org_id, ip, (user_agent or "")[:300] or None)
        if row:
            aceitos.append({"doc_key": row["doc_key"], "version": row["version"],
                            "body_sha256": row["body_sha256"], "accepted_at": row["accepted_at"]})
    return aceitos


def accept(conn: Connection, *, user_id: str, org_id: str | None, key: str,
           ip: str | None = None, user_agent: str | None = None, source: str = "web") -> dict:
    doc = conn.one("SELECT id::text AS id, title, version, status FROM legal_documents"
                   " WHERE doc_key = $1 AND status <> 'superseded'"
                   " ORDER BY version DESC LIMIT 1", ALIASES.get(key, key))
    if not doc:
        raise ApiError(404, "not_found", "Documento legal não encontrado")
    try:
        row = conn.one(
            "INSERT INTO legal_acceptances(document_id, user_id, org_id, ip, user_agent, source)"
            " VALUES ($1,$2,$3,$4,$5,$6)"
            " ON CONFLICT (document_id, user_id) DO NOTHING"
            " RETURNING id, doc_key, version, body_sha256, accepted_at",
            doc["id"], user_id, org_id, ip, (user_agent or "")[:300] or None, source)
    except IntegrityError as exc:
        # A recusa do gatilho é a mensagem útil (diz QUAL documento e em que situação está); a
        # genérica do tratador global esconderia justamente isso.
        raise ApiError(422, "document_not_effective", str(exc).split("\n")[0][:400],
                       {"doc_key": key, "status": doc["status"]}) from exc
    if not row:
        prev = conn.one("SELECT id, doc_key, version, body_sha256, accepted_at FROM legal_acceptances"
                        " WHERE document_id = $1 AND user_id = $2", doc["id"], user_id)
        return {**prev, "already_accepted": True}
    return {**row, "already_accepted": False}


def mine(conn: Connection, *, user_id: str) -> dict:
    return {"items": conn.query(
        "SELECT a.id, a.doc_key, a.version, a.body_sha256, a.accepted_at, a.source, d.title"
        " FROM legal_acceptances a JOIN legal_documents d ON d.id = a.document_id"
        " WHERE a.user_id = $1 ORDER BY a.accepted_at DESC", user_id)}


# ================================================================================================ administração
def submit_for_review(conn: Connection, *, doc_id: str) -> dict:
    return _set_status(conn, doc_id=doc_id, status="in_legal_review")


def approve(conn: Connection, *, doc_id: str, reviewed_by: str, review_reference: str,
            effective_from: Any = None) -> dict:
    """Aprova UMA versão. Exige quem revisou e sob qual referência — o CHECK do banco também exige.

    Esta função não é um atalho para aprovar sem revisão: ela registra que alguém com nome assumiu a
    revisão. Se o nome for inventado, a mentira passa a ter autor, que é o máximo que software pode
    fazer a respeito.
    """
    row = conn.one(
        "UPDATE legal_documents SET status = 'approved', reviewed_by = $2, reviewed_at = now(),"
        " review_reference = $3, effective_from = coalesce($4::date, current_date)"
        " WHERE id = $1 AND status IN ('draft','in_legal_review')"
        " RETURNING id::text AS id, doc_key, version, status, effective_from, reviewed_by",
        doc_id, reviewed_by.strip(), review_reference.strip(), effective_from)
    if not row:
        raise ApiError(422, "not_approvable",
                       "Só minuta ou documento em revisão pode ser aprovado.")
    return row


def _set_status(conn: Connection, *, doc_id: str, status: str) -> dict:
    row = conn.one("UPDATE legal_documents SET status = $2 WHERE id = $1"
                   " RETURNING id::text AS id, doc_key, version, status", doc_id, status)
    if not row:
        raise ApiError(404, "not_found", "Documento legal não encontrado")
    return row


def acceptances(conn: Connection, *, doc_key: str | None = None, limit: int = 50,
                offset: int = 0) -> dict:
    rows = conn.query(
        "SELECT a.id, a.doc_key, a.version, a.accepted_at, a.source, a.ip,"
        " left(a.body_sha256, 16) AS sha_prefix, u.email::text AS email"
        " FROM legal_acceptances a JOIN users u ON u.id = a.user_id"
        " WHERE ($1::text IS NULL OR a.doc_key = $1)"
        " ORDER BY a.accepted_at DESC LIMIT $2 OFFSET $3", doc_key, limit, offset)
    total = conn.scalar("SELECT count(*) FROM legal_acceptances"
                        " WHERE ($1::text IS NULL OR doc_key = $1)", doc_key)
    return {"items": rows, "total": total}
