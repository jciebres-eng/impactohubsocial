"""Montagem de documento: modelo → dados → evidência → validação → geração → revisão → aprovação → assinatura.

Antes, "documento" era só arquivo no cofre (upload) ou texto livre (rascunho). Agora existe um pipeline único, usado por
todos os tipos (projeto técnico, plano de trabalho, orçamento, relatório, prestação de contas, termo, contrato…), em vez
de um sistema isolado por tipo.

O que a plataforma **recusa**: gerar documento final com campo obrigatório vazio, com evidência exigida ausente, com
projeto arquivado/cancelado ou com assinatura quebrada. Em vez de gerar um documento meia-boca, a montagem fica
`blocked` e diz exatamente o que falta.
"""
from __future__ import annotations

import hashlib
from typing import Any

from ..db.pq import Connection, Json
from ..services import documents as docsvc
from ..services import formats as FMT
from ..services.audit import ledger

ENGINE_VERSION = "document-assembly@1.0.0"
BLOCKING_PROJECT_STATUS = ("archived", "cancelled", "rejected")
GENERATED_FORMATS = ("pdf", "docx", "odt")


def template(conn: Connection, template_id: str) -> dict | None:
    t = conn.one("SELECT id::text AS id, code, version, title, kind, description, data_sources, output_formats, status,"
                 " owner_org_id::text AS owner_org_id, source_note FROM document_templates WHERE id = $1", template_id)
    if not t:
        return None
    t["fields"] = conn.query("SELECT id::text AS id, section, position, key, label, help, field_type, options, required,"
                             " derived_from, requires_evidence FROM document_template_fields WHERE template_id = $1"
                             " ORDER BY section, position", template_id)
    t["sections"] = sorted({f["section"] for f in t["fields"]})
    return t


def _derive(conn: Connection, path: str, asm: dict) -> Any:
    """Valor que vem do DOMÍNIO, não digitado. `derived_from` é um caminho fechado — nunca expressão do cliente."""
    allowed = {
        "project.title": ("SELECT title FROM projects WHERE id = $1", "project_id"),
        "project.problem": ("SELECT problem FROM projects WHERE id = $1", "project_id"),
        "project.objectives": ("SELECT objectives FROM projects WHERE id = $1", "project_id"),
        "project.methodology": ("SELECT methodology FROM projects WHERE id = $1", "project_id"),
        "project.territory": ("SELECT territory FROM projects WHERE id = $1", "project_id"),
        "project.budget_total_cents": ("SELECT budget_total_cents FROM projects WHERE id = $1", "project_id"),
        "project.starts_on": ("SELECT starts_on FROM projects WHERE id = $1", "project_id"),
        "project.ends_on": ("SELECT ends_on FROM projects WHERE id = $1", "project_id"),
        "project.beneficiaries_count": ("SELECT beneficiaries_count FROM projects WHERE id = $1", "project_id"),
        "organization.legal_name": ("SELECT legal_name FROM organizations WHERE id = $1", "org_id"),
        "organization.cnpj": ("SELECT cnpj FROM organizations WHERE id = $1", "org_id"),
        "organization.city_uf": ("SELECT concat_ws('/', city, uf) FROM organizations WHERE id = $1", "org_id"),
        "diagnosis.need_statement": ("SELECT need_statement FROM diagnoses WHERE id = $1", "diagnosis_id"),
        "diagnosis.objective": ("SELECT objective FROM diagnoses WHERE id = $1", "diagnosis_id"),
    }
    spec = allowed.get(path)
    if not spec:
        return None
    sql, key = spec
    ident = asm.get(key)
    return conn.scalar(sql, ident) if ident else None


def evaluate(conn: Connection, assembly_id: str) -> dict:
    """Calcula completude e o que falta. Não grava — quem grava é `refresh`."""
    asm = conn.one("SELECT a.*, a.id::text AS id, a.template_id::text AS template_id, a.org_id::text AS org_id,"
                   " a.project_id::text AS project_id, a.diagnosis_id::text AS diagnosis_id,"
                   " p.status AS project_status FROM document_assemblies a"
                   " LEFT JOIN projects p ON p.id = a.project_id WHERE a.id = $1", assembly_id)
    if not asm:
        return {"found": False}
    tpl = template(conn, asm["template_id"])
    if not tpl:
        return {"found": False}
    values = dict(asm["values"] or {})
    evidence = dict(asm["evidence"] or {})
    missing: list[dict] = []
    filled = 0
    for f in tpl["fields"]:
        val = values.get(f["key"])
        if f["derived_from"]:
            val = _derive(conn, f["derived_from"], asm)
        has = val not in (None, "", [], {})
        if has:
            filled += 1
        elif f["required"]:
            missing.append({"kind": "field", "key": f["key"], "label": f["label"], "section": f["section"],
                            "derived_from": f["derived_from"]})
        if f["requires_evidence"]:
            doc_id = evidence.get(f["key"])
            if not doc_id:
                missing.append({"kind": "evidence", "key": f["key"], "label": f"Evidência: {f['label']}",
                                "section": f["section"]})
            else:
                ok = conn.one("SELECT status, deleted_at, valid_until FROM documents WHERE id = $1 AND org_id = $2",
                              doc_id, asm["org_id"])
                if not ok or ok["deleted_at"] is not None:
                    missing.append({"kind": "evidence_invalid", "key": f["key"],
                                    "label": f"Evidência de '{f['label']}' não está mais disponível", "section": f["section"]})
                elif ok["status"] not in docsvc.usable_statuses():
                    missing.append({"kind": "evidence_invalid", "key": f["key"],
                                    "label": f"Evidência de '{f['label']}' foi recusada na verificação de segurança",
                                    "section": f["section"]})
    total = len(tpl["fields"]) or 1
    completeness = round(100 * filled / total, 2)
    blockers: list[str] = []
    if tpl["status"] != "published":
        blockers.append("O modelo deste documento não está publicado.")
    if asm["project_status"] in BLOCKING_PROJECT_STATUS:
        blockers.append(f"O projeto está '{asm['project_status']}' — não é possível gerar documento final.")
    if [m for m in missing if m["kind"] in ("field", "evidence")]:
        blockers.append(f"{len([m for m in missing if m['kind'] in ('field', 'evidence')])} item(ns) obrigatório(s) faltando.")
    if [m for m in missing if m["kind"] == "evidence_invalid"]:
        blockers.append("Há evidência inválida anexada.")
    return {"found": True, "assembly_id": asm["id"], "template": {"id": tpl["id"], "code": tpl["code"],
            "version": tpl["version"], "title": tpl["title"], "kind": tpl["kind"], "status": tpl["status"]},
            "completeness": completeness, "filled": filled, "total": total, "missing": missing,
            "blockers": blockers, "can_generate": not blockers, "engine_version": ENGINE_VERSION}


def refresh(conn: Connection, assembly_id: str) -> dict:
    """Recalcula e grava completude/faltas/situação. Roda em contexto privilegiado (colunas guardadas)."""
    out = evaluate(conn, assembly_id)
    if not out["found"]:
        return out
    status = conn.scalar("SELECT status FROM document_assemblies WHERE id = $1", assembly_id)
    if status in ("drafting", "ready", "blocked"):
        new_status = "blocked" if out["blockers"] else ("ready" if out["can_generate"] else "drafting")
        conn.run("UPDATE document_assemblies SET completeness = $2, missing = $3::jsonb, status = $4,"
                 " blocked_reason = $5 WHERE id = $1", assembly_id, out["completeness"], Json(out["missing"]),
                 new_status, "; ".join(out["blockers"])[:1000] or None)
        out["status"] = new_status
    else:
        conn.run("UPDATE document_assemblies SET completeness = $2, missing = $3::jsonb WHERE id = $1",
                 assembly_id, out["completeness"], Json(out["missing"]))
        out["status"] = status
    return out


def _blocks(conn: Connection, tpl: dict, asm: dict) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    values = dict(asm["values"] or {})
    for section in sorted({f["section"] for f in tpl["fields"]}):
        blocks.append(("h2", section))
        for f in [x for x in tpl["fields"] if x["section"] == section]:
            val = _derive(conn, f["derived_from"], asm) if f["derived_from"] else values.get(f["key"])
            if val in (None, "", [], {}):
                continue
            if f["field_type"] == "money" and isinstance(val, int):
                text = f"R$ {val / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            elif isinstance(val, list):
                text = "; ".join(str(x) for x in val)
            elif isinstance(val, bool):
                text = "Sim" if val else "Não"
            else:
                text = str(val)
            blocks.append(("p", f"{f['label']}: {text}"))
        blocks.append(("spacer", ""))
    return blocks


def generate(conn: Connection, app, *, assembly_id: str, fmt: str, actor_user_id: str | None) -> dict:
    """Gera o arquivo e o guarda no cofre. RECUSA quando a montagem está bloqueada."""
    from ..http import ApiError
    if fmt not in GENERATED_FORMATS:
        raise ApiError(422, "format_unknown", f"Formato não suportado. Disponíveis: {', '.join(GENERATED_FORMATS)}")
    state = refresh(conn, assembly_id)
    if not state["found"]:
        raise ApiError(404, "not_found", "Montagem não encontrada")
    if not state["can_generate"]:
        raise ApiError(409, "assembly_blocked", "Não é possível gerar este documento: " + "; ".join(state["blockers"]),
                       {"missing": state["missing"], "completeness": state["completeness"]})
    asm = conn.one("SELECT a.*, a.id::text AS id, a.template_id::text AS template_id, a.org_id::text AS org_id,"
                   " a.project_id::text AS project_id, a.diagnosis_id::text AS diagnosis_id,"
                   " a.application_id::text AS application_id FROM document_assemblies a WHERE a.id = $1", assembly_id)
    tpl = template(conn, asm["template_id"])
    if fmt not in (tpl["output_formats"] or GENERATED_FORMATS):
        raise ApiError(422, "format_not_allowed", f"O modelo '{tpl['code']}' não produz {fmt}")
    blocks = _blocks(conn, tpl, asm)
    footer = (f"Gerado pela Plataforma Impacto · modelo {tpl['code']} v{tpl['version']} · montagem {asm['id'][:8]} · "
              f"completude {state['completeness']}%")
    if fmt == "pdf":
        data, mime = FMT.pdf(asm["title"], blocks, footer=footer), "application/pdf"
    elif fmt == "docx":
        data, mime = (FMT.docx(asm["title"], blocks + [("spacer", ""), ("quote", footer)]),
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    else:
        data, mime = (FMT.odt(asm["title"], blocks + [("spacer", ""), ("quote", footer)]),
                      "application/vnd.oasis.opendocument.text")
    digest = hashlib.sha256(data).hexdigest()
    key = docsvc.new_storage_key(asm["org_id"])
    app.storage.put(key, data, mime)
    from ..services.validators import safe_filename
    filename = f"{safe_filename(asm['title'])}.{fmt}"
    doc_id = conn.scalar(
        "INSERT INTO documents(org_id, project_id, application_id, doc_type, title, filename, mime_type, size_bytes,"
        " sha256, storage_key, status, scan_engine, scanned_at, origin, uploaded_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::bigint,$9,$10,'clean','generated', now(),'generated',$11) RETURNING id::text",
        asm["org_id"], asm["project_id"], asm["application_id"], f"montagem_{tpl['kind']}"[:60], asm["title"][:200],
        filename, mime, len(data), digest, key, actor_user_id)
    conn.run("UPDATE document_assemblies SET status = 'generated', generated_document_id = $2, generated_format = $3,"
             " generated_sha256 = $4, generated_at = now() WHERE id = $1", assembly_id, doc_id, fmt, digest)
    if asm["project_id"]:
        ledger(conn, project_id=asm["project_id"], org_id=asm["org_id"], actor=actor_user_id,
               entry_type="document_generated", ref_type="document", ref_id=doc_id,
               payload={"template": tpl["code"], "format": fmt, "sha256": digest, "completeness": state["completeness"]})
    return {"document_id": doc_id, "format": fmt, "sha256": digest, "filename": filename,
            "completeness": state["completeness"], "status": "generated"}


def review(conn: Connection, *, assembly_id: str, approve: bool, actor_user_id: str, note: str) -> dict:
    """Revisão e aprovação com quatro olhos: quem aprova não pode ser quem criou (CHECK no banco)."""
    from ..http import ApiError
    asm = conn.one("SELECT id::text AS id, org_id::text AS org_id, project_id::text AS project_id, status,"
                   " created_by::text AS created_by, generated_document_id::text AS generated_document_id"
                   " FROM document_assemblies WHERE id = $1", assembly_id)
    if not asm:
        raise ApiError(404, "not_found", "Montagem não encontrada")
    if asm["status"] not in ("generated", "in_review"):
        raise ApiError(409, "not_reviewable", "Só uma montagem já gerada pode ser revisada")
    if approve and asm["created_by"] == actor_user_id:
        raise ApiError(409, "four_eyes", "Quem montou o documento não pode aprová-lo. Peça a revisão a outra pessoa.")
    conn.run("UPDATE document_assemblies SET status = $2, reviewed_by = $3, reviewed_at = now(), review_note = $4,"
             " approved_by = $5, approved_at = CASE WHEN $2 = 'approved' THEN now() END WHERE id = $1",
             assembly_id, "approved" if approve else "rejected", actor_user_id, note,
             actor_user_id if approve else None)
    if approve and asm["project_id"]:
        ledger(conn, project_id=asm["project_id"], org_id=asm["org_id"], actor=actor_user_id,
               entry_type="document_approved", ref_type="document", ref_id=asm["generated_document_id"],
               payload={"assembly_id": asm["id"]})
    return {"status": "approved" if approve else "rejected"}
