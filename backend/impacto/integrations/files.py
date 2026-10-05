"""Integração por ARQUIVO: importação com pré-visualização e aprovação; exportação de datasets controlados.

Importação:  UPLOAD (cofre de documentos: tamanho, extensão, magic bytes, zip bomb, antivírus — já existentes)
             → VALIDATE → PARSE → MAP → PREVIEW → APPROVE (pessoa com papel) → IMPORT → AUDIT.
O arquivo vem SEMPRE de um `document` já validado pelo cofre (não há caminho alternativo de upload).
Importação NÃO cria usuários nem organizações (consentimento/verificação são processos próprios): ela valida, mapeia e
aplica correspondências de ID externo a registros internos existentes; o que não tem destino seguro no núcleo é dito.

Exportação:  QUERY (dataset fixo, filtrado pela organização) → TRANSFORM (CSV com neutralização de fórmula / JSON)
             → GENERATE (arquivo no storage como `document` gerado) → AUDIT → DOWNLOAD (URL temporária já existente).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile

from ..db.pq import Json
from ..http import ApiError
from ..services.audit import record as audit_record
from . import links
from .adapters.bi import DATASETS
from .contracts import ENTITIES, IntegrationError
from .mapping import map_inbound
from .xmlsafe import parse as xml_parse, to_dict

MAX_ROWS = 20_000
MAX_CELLS = 400_000
MAX_UNZIPPED = 60 * 1024 * 1024       # xlsx é zip: limite do conteúdo descomprimido (zip bomb)
FORMULA_PREFIX = ("=", "+", "-", "@", "\t", "\r")


# ------------------------------------------------------------------------------------------------ parsing (arquivo externo = não confiável)
def parse_rows(fmt: str, raw: bytes) -> list[dict]:
    if fmt == "csv":
        return _parse_csv(raw)
    if fmt == "json":
        return _parse_json(raw)
    if fmt == "xml":
        root = xml_parse(raw)
        data = to_dict(root)
        rows = _first_list(data)
        return rows[:MAX_ROWS]
    if fmt == "xlsx":
        return _parse_xlsx(raw)
    raise IntegrationError("format_unsupported", f"Formato não suportado: {fmt}", kind="permanent")


def _parse_csv(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = []
    for i, r in enumerate(reader):
        if i >= MAX_ROWS:
            raise IntegrationError("too_many_rows", f"Arquivo acima de {MAX_ROWS} linhas", kind="permanent")
        rows.append({(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items() if k is not None})
    return rows


def _parse_json(raw: bytes) -> list[dict]:
    try:
        data = json.loads(raw.decode("utf-8-sig", errors="replace"))
    except ValueError as exc:
        raise IntegrationError("json_malformed", f"JSON inválido: {exc}", kind="permanent") from exc
    rows = _first_list(data) if not isinstance(data, list) else data
    rows = [r for r in rows if isinstance(r, dict)]
    if len(rows) > MAX_ROWS:
        raise IntegrationError("too_many_rows", f"Arquivo acima de {MAX_ROWS} linhas", kind="permanent")
    return rows


def _first_list(data) -> list:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                return v
            if isinstance(v, dict):
                found = _first_list(v)
                if found:
                    return found
    return []


def _parse_xlsx(raw: bytes) -> list[dict]:
    """Leitor mínimo de XLSX (zip + XML) sem dependência nova: primeira planilha, strings compartilhadas e inline.
    Fórmulas devolvem o valor em cache (não são avaliadas). Limita tamanho descomprimido (zip bomb) e células."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise IntegrationError("xlsx_malformed", "Arquivo XLSX inválido", kind="permanent") from exc
    total = sum(i.file_size for i in zf.infolist())
    if total > MAX_UNZIPPED:
        raise IntegrationError("xlsx_too_large", "XLSX descomprimido acima do limite (possível zip bomb)", kind="permanent")
    names = zf.namelist()
    if "xl/workbook.xml" not in names:
        raise IntegrationError("xlsx_malformed", "XLSX sem workbook", kind="permanent")
    shared: list[str] = []
    if "xl/sharedStrings.xml" in names:
        for si in xml_parse(zf.read("xl/sharedStrings.xml")).iter():
            if si.tag.split("}")[-1] == "si":
                shared.append("".join(t.text or "" for t in si.iter() if t.tag.split("}")[-1] == "t"))
    sheet = next((n for n in ("xl/worksheets/sheet1.xml",) if n in names), None) or next((n for n in sorted(names) if n.startswith("xl/worksheets/sheet")), None)
    if not sheet:
        raise IntegrationError("xlsx_malformed", "XLSX sem planilha", kind="permanent")
    root = xml_parse(zf.read(sheet))
    grid: list[list[str]] = []
    cells = 0
    for row in root.iter():
        if row.tag.split("}")[-1] != "row":
            continue
        values: dict[int, str] = {}
        for cell in row:
            if cell.tag.split("}")[-1] != "c":
                continue
            cells += 1
            if cells > MAX_CELLS:
                raise IntegrationError("xlsx_too_large", f"XLSX acima de {MAX_CELLS} células", kind="permanent")
            ref = cell.get("r", "")
            col = 0
            for ch in ref:
                if ch.isalpha():
                    col = col * 26 + (ord(ch.upper()) - 64)
                else:
                    break
            t = cell.get("t")
            v_node = next((x for x in cell if x.tag.split("}")[-1] == "v"), None)
            is_node = next((x for x in cell if x.tag.split("}")[-1] == "is"), None)
            if t == "s" and v_node is not None and (v_node.text or "").isdigit():
                idx = int(v_node.text)
                val = shared[idx] if idx < len(shared) else ""
            elif t == "inlineStr" and is_node is not None:
                val = "".join(x.text or "" for x in is_node.iter() if x.tag.split("}")[-1] == "t")
            else:
                val = (v_node.text or "") if v_node is not None else ""
            values[max(col, 1) - 1] = val
        if values:
            width = max(values) + 1
            grid.append([values.get(i, "") for i in range(width)])
        if len(grid) > MAX_ROWS + 1:
            raise IntegrationError("too_many_rows", f"Planilha acima de {MAX_ROWS} linhas", kind="permanent")
    if not grid:
        return []
    header = [h.strip() or f"col{i + 1}" for i, h in enumerate(grid[0])]
    return [{header[i]: (r[i] if i < len(r) else "") for i in range(len(header))} for r in grid[1:]]


# ------------------------------------------------------------------------------------------------ pipeline de importação
# Formatos aceitos por UPLOAD: a lista é limitada pela allowlist do cofre de documentos (que valida assinatura binária).
# JSON e XML continuam suportados pelo interpretador (respostas de conexão REST/SOAP), mas NÃO por upload — enfraquecer a
# allowlist do cofre para aceitar texto sem assinatura seria perder um controle de segurança já existente.
UPLOAD_FORMATS = ("csv", "xlsx")


def create_import(app, c, *, org_id: str, user_id: str, entity: str, fmt: str, document_id: str, connection_id: str | None) -> dict:
    """UPLOAD já aconteceu no cofre. Aqui: VALIDATE (documento da própria organização, limpo) → PARSE → MAP → PREVIEW."""
    if entity not in ENTITIES:
        raise ApiError(422, "entity_invalid", "Entidade inválida")
    if fmt not in UPLOAD_FORMATS:
        raise ApiError(422, "format_not_uploadable",
                       f"Importação por arquivo aceita {', '.join(UPLOAD_FORMATS)}. JSON e XML são lidos por conexão (REST/SOAP), não por upload.")
    d = c.one("SELECT id::text AS id, filename, sha256, storage_key, status, mime_type, size_bytes FROM documents"
              " WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL", document_id, org_id)
    if not d:
        raise ApiError(404, "not_found", "Documento não encontrado")
    if d["status"] not in ("clean",) and not (d["status"] == "pending_scan" and app.settings.allow_unscanned_downloads):
        raise ApiError(409, "document_not_clean", "O arquivo ainda não passou pela verificação de segurança")
    if c.one("SELECT 1 FROM integration_imports WHERE org_id = $1 AND entity = $2 AND sha256 = $3", org_id, entity, d["sha256"]):
        raise ApiError(409, "already_imported", "Este arquivo já foi importado para esta entidade (idempotência por conteúdo)")
    mappings = c.query("SELECT entity, direction, source_path, target_field, transform, enum_map, required, default_value"
                       " FROM integration_mappings WHERE connection_id = $1 AND entity = $2", connection_id, entity) if connection_id else []
    imp_id = c.scalar("INSERT INTO integration_imports(org_id, connection_id, entity, format, document_id, filename, sha256, status, created_by)"
                      " VALUES ($1,$2,$3,$4,$5,$6,$7,'validated',$8) RETURNING id::text",
                      org_id, connection_id, entity, fmt, d["id"], d["filename"], d["sha256"], user_id)
    try:
        rows = parse_rows(fmt, app.storage.get(d["storage_key"]))
    except IntegrationError as exc:
        c.run("UPDATE integration_imports SET status = 'rejected', report = $2::jsonb WHERE id = $1", imp_id, Json({"error": exc.code, "detail": str(exc)}))
        audit_record(c, org_id=org_id, actor=user_id, action="integration.import.rejected", object_type="integration_import", object_id=imp_id,
                     payload={"error": exc.code}, ip=None, request_id=None)
        return {"id": imp_id, "status": "rejected", "error": exc.code, "detail": str(exc)}
    valid = invalid = 0
    sample_errors: list[str] = []
    for i, raw in enumerate(rows, start=1):
        if mappings:
            rec, errs = map_inbound(entity, raw, mappings)
            mapped = dict(rec.fields, external_id=rec.external_id, external_version=rec.external_version)
        else:
            mapped, errs = dict(raw), ["sem mapeamento configurado para a conexão: linhas só pré-visualizadas"]
        ok = not errs
        valid += ok
        invalid += not ok
        if errs and len(sample_errors) < 20:
            sample_errors.append(f"linha {i}: " + "; ".join(errs)[:200])
        c.run("INSERT INTO integration_import_rows(import_id, row_no, raw, mapped, valid, errors) VALUES ($1,$2,$3::jsonb,$4::jsonb,$5,$6::text[])",
              imp_id, i, Json(_sanitize(raw)), Json(_sanitize(mapped)), ok, errs[:10])
    report = {"columns": sorted({k for r in rows[:50] for k in r})[:60], "sample_errors": sample_errors, "mappings": len(mappings)}
    c.run("UPDATE integration_imports SET status = 'previewed', rows_total = $2, rows_valid = $3, rows_invalid = $4, report = $5::jsonb WHERE id = $1",
          imp_id, len(rows), valid, invalid, Json(report))
    audit_record(c, org_id=org_id, actor=user_id, action="integration.import.previewed", object_type="integration_import", object_id=imp_id,
                 payload={"entity": entity, "format": fmt, "rows": len(rows), "valid": valid, "invalid": invalid}, ip=None, request_id=None)
    return {"id": imp_id, "status": "previewed", "rows_total": len(rows), "rows_valid": valid, "rows_invalid": invalid, "report": report}


def _sanitize(d: dict) -> dict:
    out = {}
    for k, v in (d or {}).items():
        key = str(k)[:100]
        if isinstance(v, (dict, list)):
            out[key] = json.loads(json.dumps(v, default=str))[:50] if isinstance(v, list) else {str(a)[:100]: str(b)[:500] for a, b in list(v.items())[:50]}
        else:
            out[key] = v if isinstance(v, (int, float, bool)) or v is None else str(v)[:2000]
    return out


def preview(c, *, org_id: str, import_id: str, limit: int = 50) -> dict:
    imp = c.one("SELECT id::text AS id, entity, format, filename, status, rows_total, rows_valid, rows_invalid, report, approved_at, created_at"
                " FROM integration_imports WHERE id = $1 AND org_id = $2", import_id, org_id)
    if not imp:
        raise ApiError(404, "not_found", "Importação não encontrada")
    imp["rows"] = c.query("SELECT row_no, raw, mapped, valid, errors FROM integration_import_rows WHERE import_id = $1 ORDER BY row_no LIMIT $2", import_id, limit)
    return imp


def approve_and_import(c, *, org_id: str, user_id: str, import_id: str, connection_id_override: str | None = None) -> dict:
    """APPROVE → IMPORT → AUDIT. Só linhas válidas são aplicadas; cada aplicação é uma correspondência de ID externo
    para um registro interno EXISTENTE (`internal_id` + `external_id`). Nada é criado por suposição."""
    imp = c.one("SELECT id::text AS id, entity, status, connection_id::text AS connection_id, created_by::text AS created_by, rows_valid"
                " FROM integration_imports WHERE id = $1 AND org_id = $2 FOR UPDATE", import_id, org_id)
    if not imp:
        raise ApiError(404, "not_found", "Importação não encontrada")
    if imp["status"] != "previewed":
        raise ApiError(409, "invalid_state", f"Importação em estado '{imp['status']}' não pode ser aprovada")
    conn_id = imp["connection_id"] or connection_id_override
    rows = c.query("SELECT row_no, mapped FROM integration_import_rows WHERE import_id = $1 AND valid ORDER BY row_no", import_id)
    applied = skipped = conflicts = 0
    reasons: dict[str, int] = {}
    for r in rows:
        m = r["mapped"] or {}
        internal_id, external_id = m.get("internal_id"), m.get("external_id")
        if not conn_id or not internal_id or not external_id:
            skipped += 1
            reasons["sem_conexao_ou_sem_ids"] = reasons.get("sem_conexao_ou_sem_ids", 0) + 1
            continue
        out = links.link(c, org_id=org_id, connection_id=conn_id, entity=imp["entity"], internal_id=str(internal_id),
                         external_id=str(external_id), external_version=m.get("external_version"))
        if out["status"] == "conflict":
            conflicts += 1
        else:
            applied += 1
    status = "imported" if applied or not rows else ("imported" if skipped and not conflicts else "imported")
    c.run("UPDATE integration_imports SET status = $2, rows_imported = $3, approved_by = $4, approved_at = now(),"
          " report = report || $5::jsonb WHERE id = $1", import_id, status, applied, user_id,
          Json({"applied_links": applied, "conflicts": conflicts, "skipped": skipped, "skip_reasons": reasons,
                "note": "Importação aplica correspondências de ID externo a registros existentes; não cria usuários nem organizações."}))
    audit_record(c, org_id=org_id, actor=user_id, action="integration.import.approved", object_type="integration_import", object_id=import_id,
                 payload={"entity": imp["entity"], "applied_links": applied, "conflicts": conflicts, "skipped": skipped}, ip=None, request_id=None)
    return {"id": import_id, "status": status, "applied_links": applied, "conflicts": conflicts, "skipped": skipped, "skip_reasons": reasons}


# ------------------------------------------------------------------------------------------------ exportação / datasets
def _csv_cell(v) -> str:
    s = "" if v is None else str(v)
    return ("'" + s) if s[:1] in FORMULA_PREFIX else s          # neutraliza injeção de fórmula em planilhas


def generate_export(app, c, *, org_id: str, user_id: str, dataset: str, fmt: str, filters: dict | None = None) -> dict:
    """QUERY → TRANSFORM → GENERATE → AUDIT. O arquivo nasce como `document` gerado (download pela URL temporária existente)."""
    if dataset not in DATASETS:
        raise ApiError(422, "dataset_unknown", f"Dataset desconhecido. Disponíveis: {', '.join(sorted(DATASETS))}")
    exp_id = c.scalar("INSERT INTO integration_exports(org_id, dataset, format, filters, status, requested_by) VALUES ($1,$2,$3,$4::jsonb,'running',$5) RETURNING id::text",
                      org_id, dataset, fmt, Json(filters or {}), user_id)
    _, sql = DATASETS[dataset]
    rows = c.query(sql + " LIMIT 50000", org_id)
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        cols = list(rows[0].keys()) if rows else []
        w.writerow(cols)
        for r in rows:
            w.writerow([_csv_cell(r[k]) for k in cols])
        data, mime, ext = buf.getvalue().encode("utf-8-sig"), "text/csv", "csv"
    else:
        data, mime, ext = json.dumps({"dataset": dataset, "rows": rows}, ensure_ascii=False, default=str).encode(), "application/json", "json"
    from ..services.documents import new_storage_key
    key = new_storage_key(org_id)
    app.storage.put(key, data, mime)
    digest = hashlib.sha256(data).hexdigest()
    filename = f"{dataset}-{exp_id[:8]}.{ext}"
    did = c.scalar("INSERT INTO documents(org_id, doc_type, title, filename, mime_type, size_bytes, sha256, storage_key, status, scan_engine, scanned_at,"
                   " origin, uploaded_by) VALUES ($1,'exportacao_dados',$2,$3,$4,$5::bigint,$6,$7,'clean','generated', now(),'generated',$8) RETURNING id::text",
                   org_id, f"Exportação {dataset}"[:200], filename, mime, max(1, len(data)), digest, key, user_id)
    c.run("UPDATE integration_exports SET status = 'ready', rows = $2, document_id = $3, finished_at = now() WHERE id = $1", exp_id, len(rows), did)
    audit_record(c, org_id=org_id, actor=user_id, action="integration.export.generated", object_type="integration_export", object_id=exp_id,
                 payload={"dataset": dataset, "format": fmt, "rows": len(rows), "sha256": digest}, ip=None, request_id=None)
    return {"id": exp_id, "status": "ready", "rows": len(rows), "document_id": did, "filename": filename, "sha256": digest}
