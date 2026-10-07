"""Motor de proveniência: de onde veio este número.

A REGRA

    "Nenhum indicador crítico deveria existir sem conseguir apontar para sua origem/evidência."

O que o produto registrava até a v0.22.0 era o RESULTADO: `indicador = 87`. O que faltava era
responder *de onde veio o 87* numa única consulta — projeto, indicador, linha de base e a fonte
dela, evidência, documento com hash de conteúdo e versão, quem enviou, quem revisou, quem validou
e de qual organização, mais os lançamentos do Impact Ledger e os eventos de auditoria ligados.

O QUE ESTE MOTOR NÃO FAZ

Não preenche lacuna. Se a medição não tem evidência, a resposta diz que não tem, em `gaps`, com o
texto que a interface mostra. Uma cadeia de proveniência que esconde o elo que falta é pior que
nenhuma: ela transforma ausência de prova em aparência de prova.

`provenance_complete` é verdadeiro só quando TODOS os elos existem. É o campo que a interface usa
para decidir entre "rastreável até a evidência" e "rastreável até onde o registro alcança".
"""
from __future__ import annotations

from typing import Any


def indicator_value(c, value_id: str) -> dict[str, Any] | None:
    """Cadeia completa de um valor de indicador. `None` se o valor não existe (ou a RLS o esconde)."""
    v = c.one(
        "SELECT iv.id::text AS id, iv.value, iv.measured_on, iv.status, iv.source_kind, iv.note,"
        "       iv.created_at, iv.evidence_id::text AS evidence_id,"
        "       iv.created_by::text AS created_by, cu.full_name AS created_by_name,"
        "       iv.validated_by::text AS validated_by, vu.full_name AS validated_by_name,"
        "       iv.validated_by_org::text AS validated_by_org, vo.legal_name AS validated_by_org_name,"
        "       pi.id::text AS project_indicator_id, pi.baseline, pi.baseline_source, pi.baseline_date,"
        "       pi.target, pi.target_date, pi.method, pi.created_at AS indicator_attached_at,"
        "       i.code AS indicator_code, i.name AS indicator_name, i.unit AS indicator_unit,"
        "       p.id::text AS project_id, p.title AS project_title, p.created_at AS project_created_at,"
        "       o.id::text AS org_id, o.legal_name AS org_name"
        "  FROM indicator_values iv"
        "  JOIN project_indicators pi ON pi.id = iv.project_indicator_id"
        "  JOIN indicator_catalog i ON i.id = pi.indicator_id"
        "  JOIN projects p ON p.id = iv.project_id"
        "  JOIN organizations o ON o.id = iv.org_id"
        "  LEFT JOIN users cu ON cu.id = iv.created_by"
        "  LEFT JOIN users vu ON vu.id = iv.validated_by"
        "  LEFT JOIN organizations vo ON vo.id = iv.validated_by_org"
        " WHERE iv.id = $1", value_id)
    if not v:
        return None

    ev = None
    if v["evidence_id"]:
        ev = c.one(
            "SELECT e.id::text AS id, e.kind, e.title, e.description, e.occurred_on, e.status,"
            "       e.created_at, e.created_by::text AS created_by, su.full_name AS submitted_by_name,"
            "       e.reviewed_by::text AS reviewed_by, ru.full_name AS reviewed_by_name,"
            "       e.reviewed_by_org::text AS reviewed_by_org, ro.legal_name AS reviewed_by_org_name,"
            "       e.reviewed_at, e.review_note, e.document_id::text AS document_id"
            "  FROM evidences e"
            "  LEFT JOIN users su ON su.id = e.created_by"
            "  LEFT JOIN users ru ON ru.id = e.reviewed_by"
            "  LEFT JOIN organizations ro ON ro.id = e.reviewed_by_org"
            " WHERE e.id = $1", v["evidence_id"])

    doc = None
    if ev and ev["document_id"]:
        doc = c.one(
            "SELECT d.id::text AS id, d.title, d.filename, d.mime_type, d.size_bytes, d.sha256,"
            "       d.doc_type, d.status, d.version, d.supersedes_id::text AS supersedes_id,"
            "       d.origin, d.origin_source, d.issued_on, d.valid_until, d.created_at,"
            "       d.uploaded_by::text AS uploaded_by, uu.full_name AS uploaded_by_name,"
            "       d.validation_status, d.validated_by::text AS validated_by,"
            "       vu.full_name AS validated_by_name, d.validated_at, d.validation_note,"
            "       (SELECT count(*) FROM documents s WHERE s.supersedes_id = d.id) AS superseded_by_count"
            "  FROM documents d"
            "  LEFT JOIN users uu ON uu.id = d.uploaded_by"
            "  LEFT JOIN users vu ON vu.id = d.validated_by"
            " WHERE d.id = $1", ev["document_id"])

    # Impact Ledger: os lançamentos que CITAM este valor. `seq` e `entry_hash` entram porque é o que
    # torna o elo conferível — a cadeia de hash do projeto pode ser verificada com `ledger_verify()`.
    lancamentos = c.query(
        "SELECT seq, entry_type, amount_cents, at, entry_hash, reverses_id,"
        "       actor_user_id::text AS actor_user_id"
        "  FROM ledger_entries WHERE ref_type = 'indicator_value' AND ref_id = $1"
        " ORDER BY seq", value_id)

    eventos = c.query(
        "SELECT seq, action, at, actor_user_id::text AS actor_user_id, ip::text AS ip, request_id"
        "  FROM audit_events WHERE object_type = 'indicator_value' AND object_id = $1"
        " ORDER BY seq", value_id)

    lacunas = _gaps(v, ev, doc, lancamentos, eventos)
    return {
        "value": {k: v[k] for k in ("id", "value", "measured_on", "status", "source_kind", "note",
                                     "created_at", "created_by", "created_by_name")},
        "indicator": {
            "project_indicator_id": v["project_indicator_id"], "code": v["indicator_code"],
            "name": v["indicator_name"], "unit": v["indicator_unit"],
            "baseline": v["baseline"], "baseline_source": v["baseline_source"],
            "baseline_date": v["baseline_date"], "target": v["target"],
            "target_date": v["target_date"], "method": v["method"],
            "attached_at": v["indicator_attached_at"]},
        "project": {"id": v["project_id"], "title": v["project_title"],
                    "created_at": v["project_created_at"],
                    "org_id": v["org_id"], "org_name": v["org_name"]},
        "evidence": ev,
        "document": doc,
        "validation": None if not v["validated_by"] else {
            "validated_by": v["validated_by"], "validated_by_name": v["validated_by_name"],
            "validated_by_org": v["validated_by_org"],
            "validated_by_org_name": v["validated_by_org_name"],
            "independent": v["validated_by_org"] != v["org_id"]},
        "ledger": lancamentos,
        "audit": eventos,
        "chain": _chain(v, ev, doc, lancamentos),
        "gaps": lacunas,
        "provenance_complete": not lacunas,
    }


def _gaps(v, ev, doc, lancamentos, eventos) -> list[dict[str, str]]:
    """Cada lacuna é nomeada em português, com o efeito dela sobre o que o número prova."""
    fora: list[dict[str, str]] = []
    if not ev:
        fora.append({"link": "evidencia",
                     "what": "A medição não aponta para nenhuma evidência.",
                     "effect": "O número é autodeclarado. O banco impede que ele seja apresentado "
                               "como validado."})
    elif not doc:
        fora.append({"link": "documento",
                     "what": "A evidência existe, mas não tem documento anexado.",
                     "effect": "Há descrição do que aconteceu, não há arquivo para conferir."})
    if doc and not doc["sha256"]:
        fora.append({"link": "hash",
                     "what": "O documento não tem hash de conteúdo registrado.",
                     "effect": "Não é possível provar que o arquivo guardado é o que foi enviado."})
    if ev and not ev["reviewed_by"]:
        fora.append({"link": "revisao",
                     "what": "A evidência não foi revisada por ninguém.",
                     "effect": "O arquivo existe; ninguém atestou que ele sustenta o número."})
    if not v["baseline_source"]:
        fora.append({"link": "linha_de_base",
                     "what": "O indicador do projeto não declara a fonte da linha de base.",
                     "effect": "A variação medida não tem ponto de partida conferível."})
    if not v["method"]:
        fora.append({"link": "metodo",
                     "what": "O indicador do projeto não declara método de medição.",
                     "effect": "Dois medidores podem chegar a números diferentes sem errar."})
    if v["status"] == "validated" and v["validated_by_org"] == v["org_id"]:
        fora.append({"link": "independencia",
                     "what": "A validação foi feita pela própria organização medida.",
                     "effect": "Validação não independente. O banco recusa este estado; se ele "
                               "aparecer, é indício de alteração direta no banco."})
    if not lancamentos:
        fora.append({"link": "ledger",
                     "what": "Nenhum lançamento do Impact Ledger cita esta medição.",
                     "effect": "A medição não entra na cadeia de hash do projeto, então não é "
                               "coberta por `ledger_verify()`."})
    return fora


def _chain(v, ev, doc, lancamentos) -> list[dict[str, Any]]:
    """A cadeia em ordem cronológica, como a interface a desenha. Elo ausente aparece como ausente."""
    passos: list[dict[str, Any]] = [
        {"step": "projeto", "what": v["project_title"], "who": v["org_name"],
         "when": v["project_created_at"], "present": True},
        {"step": "indicador", "what": f'{v["indicator_code"]} — {v["indicator_name"]}',
         "who": v["org_name"], "when": v["indicator_attached_at"], "present": True},
        {"step": "linha_de_base",
         "what": v["baseline_source"] or "fonte da linha de base não declarada",
         "who": None, "when": v["baseline_date"], "present": bool(v["baseline_source"])},
    ]
    if doc:
        passos.append({"step": "documento",
                       "what": f'{doc["filename"]} (versão {doc["version"]}, sha256 '
                               f'{(doc["sha256"] or "")[:12]}…)',
                       "who": doc["uploaded_by_name"], "when": doc["created_at"], "present": True})
    else:
        passos.append({"step": "documento", "what": "nenhum documento anexado",
                       "who": None, "when": None, "present": False})
    if ev:
        passos.append({"step": "evidencia", "what": ev["title"], "who": ev["submitted_by_name"],
                       "when": ev["created_at"], "present": True})
        passos.append({"step": "revisao",
                       "what": ev["review_note"] or ("evidência " + (ev["status"] or "")),
                       "who": ev["reviewed_by_org_name"] or ev["reviewed_by_name"],
                       "when": ev["reviewed_at"], "present": bool(ev["reviewed_by"])})
    else:
        passos.append({"step": "evidencia", "what": "nenhuma evidência apontada",
                       "who": None, "when": None, "present": False})
    passos.append({"step": "medicao",
                   "what": f'{v["value"]} {v["indicator_unit"] or ""}'.strip()
                           + f' em {v["measured_on"]}',
                   "who": v["created_by_name"], "when": v["created_at"], "present": True})
    passos.append({"step": "validacao",
                   "what": v["status"],
                   "who": v["validated_by_org_name"] or v["validated_by_name"],
                   "when": None, "present": bool(v["validated_by"])})
    for lancamento in lancamentos:
        passos.append({"step": "ledger",
                       "what": f'{lancamento["entry_type"]} (seq {lancamento["seq"]}, hash '
                               f'{(lancamento["entry_hash"] or "")[:12]}…)',
                       "who": None, "when": lancamento["at"], "present": True})
    return passos
