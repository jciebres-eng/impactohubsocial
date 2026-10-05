"""Montagem de documento (modelo → campos → evidência → completude → BLOQUEIO → geração → revisão) e a
administração de chaves, provedores de assinatura e política de assinatura.

Duas recusas que são o ponto do módulo:

* Montagem incompleta NÃO gera documento. A resposta é 409 com a lista do que falta e a completude — nunca um
  arquivo com lacuna disfarçada de texto pronto.
* Provedor de assinatura só assina quando o estado dele é ``production``. Enquanto depende de contratação, o estado é
  ``unavailable`` e um gatilho no banco recusa a assinatura. Não existe "assinatura ICP-Brasil simulada" aqui.
"""
from __future__ import annotations

from ..core import assembly as AS
from ..core import keys as KEYS
from ..db.pq import Json
from ..http import ApiError, Ctx, not_found, page, route
from . import core_schemas as C

T = ("documents",)
TA = ("admin",)


def _own_assembly(c, ctx: Ctx, aid: str) -> dict:
    a = c.one("SELECT id::text AS id, org_id::text AS org_id, template_id::text AS template_id, title, status,"
              " completeness, created_by::text AS created_by FROM document_assemblies WHERE id = $1 AND org_id = $2",
              aid, ctx.org_id)
    if not a:
        raise not_found("Montagem")
    return a


# ------------------------------------------------------------------------------------------------ modelos
@route("GET", "/v1/document-templates", query=C.TemplateQ, min_role="viewer", tags=T,
       summary="Modelos de documento da plataforma e os da própria organização")
def list_templates(ctx: Ctx, q: C.TemplateQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, code, version, title, kind, description, data_sources, output_formats,"
                       " status, owner_org_id::text AS owner_org_id, source_note, published_at,"
                       " (SELECT count(*) FROM document_template_fields f WHERE f.template_id = t.id) AS fields"
                       " FROM document_templates t WHERE ($1::text IS NULL OR kind = $1)"
                       " AND ($2::text IS NULL OR status = $2) ORDER BY kind, code, version LIMIT $3 OFFSET $4",
                       q.kind, q.status, q.limit + 1, q.offset)
    out = page(rows, q.limit, q.offset)
    out["note"] = "Modelo com owner_org_id nulo é da plataforma. Modelo publicado é imutável: mudar exige nova versão."
    return out


@route("GET", "/v1/document-templates/{template_id}", min_role="viewer", tags=T,
       summary="Modelo com seções, campos e o que cada campo exige de evidência")
def get_template(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        t = AS.template(c, ctx.path["template_id"])
    if not t:
        raise not_found("Modelo")
    return t


@route("POST", "/v1/document-templates", body=C.TemplateIn, min_role="admin", status=201, tags=T,
       summary="Cria um modelo próprio da organização (nasce em rascunho)")
def create_template(ctx: Ctx, body: C.TemplateIn):
    d = body.model_dump()
    with ctx.tx() as c:
        if c.one("SELECT 1 FROM document_templates WHERE code = $1 AND version = $2", d["code"], d["version"]):
            raise ApiError(409, "already_exists", f"Já existe o modelo '{d['code']}' na versão {d['version']}")
        tid = c.scalar("INSERT INTO document_templates(code, version, title, kind, description, data_sources,"
                       " output_formats, owner_org_id, source_note) VALUES ($1,$2,$3,$4,$5,$6::text[],$7::text[],$8,$9)"
                       " RETURNING id::text", d["code"], d["version"], d["title"], d["kind"], d["description"],
                       d["data_sources"], d["output_formats"], ctx.org_id, d["source_note"])
        ctx.audit(c, "document_template.created", "document_template", tid, {"code": d["code"]})
    return {"id": tid, "status": "draft"}


@route("POST", "/v1/document-templates/{template_id}/fields", body=C.TemplateFieldIn, min_role="admin", status=201,
       tags=T, summary="Adiciona campo ao modelo (recusado depois de publicado)")
def add_template_field(ctx: Ctx, body: C.TemplateFieldIn):
    tid, d = ctx.path["template_id"], body.model_dump()
    with ctx.tx() as c:
        t = c.one("SELECT id::text AS id, status, owner_org_id::text AS owner_org_id FROM document_templates"
                  " WHERE id = $1", tid)
        if not t or t["owner_org_id"] != ctx.org_id:
            raise not_found("Modelo")
        if t["status"] == "published":
            raise ApiError(409, "template_published",
                           "Modelo publicado é imutável. Crie uma nova versão do modelo para alterar os campos.")
        if d["derived_from"] and d["derived_from"] not in AS.DERIVABLE:
            raise ApiError(422, "derived_unknown",
                           f"'{d['derived_from']}' não é um caminho de domínio conhecido.",
                           {"available": sorted(AS.DERIVABLE)})
        if c.one("SELECT 1 FROM document_template_fields WHERE template_id = $1 AND key = $2", tid, d["key"]):
            raise ApiError(409, "already_exists", f"O campo '{d['key']}' já existe neste modelo")
        fid = c.scalar("INSERT INTO document_template_fields(template_id, section, position, key, label, help,"
                       " field_type, options, required, derived_from, requires_evidence)"
                       " VALUES ($1,$2,$3::smallint,$4,$5,$6,$7,$8::jsonb,$9,$10,$11) RETURNING id::text",
                       tid, d["section"], d["position"], d["key"], d["label"], d["help"], d["field_type"],
                       Json(d["options"]), d["required"], d["derived_from"], d["requires_evidence"])
        ctx.audit(c, "document_template.field_added", "document_template", tid, {"key": d["key"]})
    return {"id": fid}


@route("POST", "/v1/document-templates/{template_id}/publish", min_role="admin", tags=T,
       summary="Publica o modelo (a partir daqui ele não muda mais)")
def publish_template(ctx: Ctx):
    tid = ctx.path["template_id"]
    # `status`/`published_by`/`published_at` são colunas guardadas: a publicação é um passo privilegiado explícito.
    with ctx.system_tx() as c:
        t = c.one("SELECT id::text AS id, status, owner_org_id::text AS owner_org_id FROM document_templates"
                  " WHERE id = $1", tid)
        if not t or t["owner_org_id"] != ctx.org_id:
            raise not_found("Modelo")
        if t["status"] == "published":
            return {"id": tid, "status": "published", "changed": False}
        n = c.scalar("SELECT count(*) FROM document_template_fields WHERE template_id = $1", tid) or 0
        if n == 0:
            raise ApiError(409, "template_empty", "Um modelo sem campos não pode ser publicado.")
        c.run("UPDATE document_templates SET status = 'published', published_by = $2, published_at = now()"
              " WHERE id = $1", tid, ctx.user_id)
        ctx.audit(c, "document_template.published", "document_template", tid, {"fields": n})
    return {"id": tid, "status": "published", "changed": True, "fields": n}


@route("GET", "/v1/document-assembly-reference", min_role="viewer", tags=T,
       summary="Como a montagem funciona: caminhos de domínio, situações e o que bloqueia a geração")
def assembly_reference(ctx: Ctx):
    return {"engine_version": AS.ENGINE_VERSION, "derivable_paths": sorted(AS.DERIVABLE),
            "formats": list(AS.GENERATED_FORMATS), "blocking_project_status": list(AS.BLOCKING_PROJECT_STATUS),
            "statuses": {"drafting": "em preenchimento", "ready": "pronta para gerar", "blocked": "bloqueada",
                         "generated": "documento gerado", "in_review": "em revisão", "approved": "aprovada",
                         "rejected": "recusada na revisão", "signed": "assinada", "archived": "arquivada"},
            "note": "O valor derivado vem do domínio por caminho fechado — nunca de expressão enviada pelo cliente."}


# ------------------------------------------------------------------------------------------------ montagens
@route("GET", "/v1/document-assemblies", query=C.AssemblyQ, min_role="viewer", tags=T)
def list_assemblies(ctx: Ctx, q: C.AssemblyQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT a.id::text AS id, a.title, a.status, a.completeness, a.missing, a.blocked_reason,"
                       " a.generated_format, a.generated_at, a.generated_document_id::text AS generated_document_id,"
                       " a.project_id::text AS project_id, a.created_at, a.updated_at, t.code AS template_code,"
                       " t.version AS template_version, t.kind AS template_kind FROM document_assemblies a"
                       " JOIN document_templates t ON t.id = a.template_id WHERE a.org_id = $1"
                       " AND ($2::uuid IS NULL OR a.project_id = $2) AND ($3::text IS NULL OR a.status = $3)"
                       " ORDER BY a.updated_at DESC LIMIT $4 OFFSET $5",
                       ctx.org_id, q.project_id, q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/document-assemblies", body=C.AssemblyIn, min_role="member", status=201, tags=T,
       summary="Abre uma montagem a partir de um modelo publicado")
def create_assembly(ctx: Ctx, body: C.AssemblyIn):
    d = body.model_dump()
    with ctx.tx() as c:
        t = c.one("SELECT id::text AS id, status, owner_org_id::text AS owner_org_id FROM document_templates"
                  " WHERE id = $1", d["template_id"])
        if not t:
            raise not_found("Modelo")
        if t["status"] != "published":
            raise ApiError(409, "template_not_published", "Só um modelo publicado pode ser usado para montar documento.")
        for field, table, label in (("project_id", "projects", "Projeto"), ("diagnosis_id", "diagnoses", "Diagnóstico"),
                                    ("application_id", "applications", "Candidatura")):
            if d[field] and not c.one(f"SELECT 1 FROM {table} WHERE id = $1 AND org_id = $2", d[field], ctx.org_id):
                raise not_found(label)
        aid = c.scalar("INSERT INTO document_assemblies(template_id, org_id, project_id, diagnosis_id,"
                       " application_id, title, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id::text",
                       d["template_id"], ctx.org_id, d["project_id"], d["diagnosis_id"], d["application_id"],
                       d["title"], ctx.user_id)
        ctx.audit(c, "document_assembly.created", "document_assembly", aid, {"template_id": d["template_id"]})
    # a avaliação já grava completude e situação (colunas guardadas) no mesmo pedido
    with ctx.system_tx() as c:
        state = AS.refresh(c, aid)
    return {"id": aid, "status": state["status"], "completeness": state["completeness"], "missing": state["missing"]}


@route("GET", "/v1/document-assemblies/{assembly_id}", min_role="viewer", tags=T,
       summary="Montagem com campos, valores, evidência, completude e o que impede a geração")
def get_assembly(ctx: Ctx):
    aid = ctx.path["assembly_id"]
    with ctx.tx(readonly=True) as c:
        a = c.one("SELECT a.*, a.id::text AS id, a.template_id::text AS template_id, a.org_id::text AS org_id,"
                  " a.project_id::text AS project_id, a.diagnosis_id::text AS diagnosis_id,"
                  " a.application_id::text AS application_id,"
                  " a.generated_document_id::text AS generated_document_id, a.created_by::text AS created_by,"
                  " a.reviewed_by::text AS reviewed_by, a.approved_by::text AS approved_by,"
                  " user_display_name(a.created_by) AS created_by_name,"
                  " user_display_name(a.reviewed_by) AS reviewed_by_name FROM document_assemblies a"
                  " WHERE a.id = $1 AND a.org_id = $2", aid, ctx.org_id)
        if not a:
            raise not_found("Montagem")
        a["template"] = AS.template(c, a["template_id"])
        a["evaluation"] = AS.evaluate(c, aid)
    return a


@route("PUT", "/v1/document-assemblies/{assembly_id}", body=C.AssemblyUpdateIn, min_role="member", tags=T,
       summary="Preenche a montagem (completude e situação são recalculadas pelo servidor)")
def update_assembly(ctx: Ctx, body: C.AssemblyUpdateIn):
    aid = ctx.path["assembly_id"]
    d = body.model_dump(exclude_none=True)
    if not d:
        raise ApiError(422, "validation_error", "Nada para atualizar")
    with ctx.tx() as c:
        a = _own_assembly(c, ctx, aid)
        if a["status"] not in ("drafting", "ready", "blocked", "rejected"):
            raise ApiError(409, "not_editable",
                           f"Montagem na situação '{a['status']}' não é editável. Abra uma nova montagem.")
        if "evidence" in d:
            for key, doc in d["evidence"].items():
                if not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL",
                             doc, ctx.org_id):
                    raise ApiError(404, "not_found", f"Documento de evidência do campo '{key}' não encontrado")
        sets, args = [], [aid]
        for col in ("title", "values", "evidence"):
            if col in d:
                args.append(Json(d[col]) if col in ("values", "evidence") else d[col])
                sets.append(f"{col} = ${len(args)}" + ("::jsonb" if col in ("values", "evidence") else ""))
        if a["status"] == "rejected":
            sets.append("status = 'drafting'")
        c.run(f"UPDATE document_assemblies SET {', '.join(sets)} WHERE id = $1", *args)
        ctx.audit(c, "document_assembly.updated", "document_assembly", aid, {"fields": sorted(d)})
    with ctx.system_tx() as c:
        state = AS.refresh(c, aid)
    return {"id": aid, "status": state["status"], "completeness": state["completeness"],
            "missing": state["missing"], "blockers": state["blockers"], "can_generate": state["can_generate"]}


@route("POST", "/v1/document-assemblies/{assembly_id}/generate", body=C.GenerateIn, min_role="member", tags=T,
       summary="Gera o documento (RECUSA quando falta campo obrigatório ou evidência)")
def generate_assembly(ctx: Ctx, body: C.GenerateIn):
    aid = ctx.path["assembly_id"]
    with ctx.tx(readonly=True) as c:
        _own_assembly(c, ctx, aid)
    with ctx.system_tx() as c:
        out = AS.generate(c, ctx.app, assembly_id=aid, fmt=body.format, actor_user_id=ctx.user_id)
        ctx.audit(c, "document_assembly.generated", "document", out["document_id"],
                  {"assembly_id": aid, "format": body.format, "sha256": out["sha256"]})
    return out


@route("POST", "/v1/document-assemblies/{assembly_id}/review", body=C.ReviewIn, min_role="member", tags=T,
       summary="Revisa a montagem (quem montou não aprova: quatro olhos, com CHECK no banco)")
def review_assembly(ctx: Ctx, body: C.ReviewIn):
    aid = ctx.path["assembly_id"]
    with ctx.tx(readonly=True) as c:
        _own_assembly(c, ctx, aid)
    with ctx.system_tx() as c:
        out = AS.review(c, assembly_id=aid, approve=body.approve, actor_user_id=ctx.user_id, note=body.note)
        ctx.audit(c, "document_assembly.reviewed", "document_assembly", aid, {"approved": body.approve})
    return out


# ------------------------------------------------------------------------------------------------ assinatura
@route("GET", "/v1/signature-providers", min_role="viewer", tags=("trust",),
       summary="Provedores de assinatura e o estado REAL de cada um (o que depende de contratação diz isso)")
def signature_providers(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT key, name, legal_level, crypto_level, method, identity_level_required,"
                       " supports_timestamp, supports_revocation_check, supports_certificate, state,"
                       " external_dependency, activation_note, health_state, health_detail, last_health_at"
                       " FROM signature_providers ORDER BY legal_level DESC, key")
    return {"items": rows,
            "legal_levels": {"simple": "assinatura eletrônica simples",
                             "advanced": "assinatura eletrônica avançada (Lei 14.063/2020)",
                             "qualified": "assinatura eletrônica qualificada — exige certificado ICP-Brasil real"},
            "crypto_levels": {"server_hmac": "selo HMAC do servidor — não é assinatura de chave assimétrica",
                              "asymmetric_pkcs7": "assinatura assimétrica PKCS#7",
                              "asymmetric_pades": "assinatura assimétrica PAdES", "none": "sem criptografia própria"},
            "note": "Só provedor em estado 'production' assina. Enquanto depende de contratação, o estado é "
                    "'unavailable' e a assinatura é recusada pelo banco — não existe assinatura simulada."}


@route("GET", "/v1/signature-policies", min_role="viewer", tags=("trust",),
       summary="Política de assinatura por tipo de documento (padrão da plataforma + a da organização)")
def list_signature_policies(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, org_id::text AS org_id, doc_kind, min_legal_level, min_identity_level,"
                       " require_timestamp, note FROM signature_policies"
                       " WHERE org_id IS NULL OR org_id = $1 ORDER BY doc_kind, org_id NULLS FIRST", ctx.org_id)
    return {"items": rows, "note": "A política da organização prevalece sobre a padrão para o mesmo tipo."}


@route("PUT", "/v1/signature-policies", body=C.SignaturePolicyIn, min_role="admin", tags=("trust",),
       summary="Define a política de assinatura da organização")
def set_signature_policy(ctx: Ctx, body: C.SignaturePolicyIn):
    d = body.model_dump()
    with ctx.tx() as c:
        avail = c.query("SELECT key, legal_level FROM signature_providers WHERE state = 'production'")
        levels = {"simple": 0, "advanced": 1, "qualified": 2}
        if not any(levels[a["legal_level"]] >= levels[d["min_legal_level"]] for a in avail):
            raise ApiError(409, "level_unavailable",
                           f"Nenhum provedor em produção entrega o nível '{d['min_legal_level']}'. "
                           "Exigir esse nível bloquearia toda assinatura deste tipo de documento.",
                           {"available": avail})
        c.run("INSERT INTO signature_policies(org_id, doc_kind, min_legal_level, min_identity_level,"
              " require_timestamp, note, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7)"
              " ON CONFLICT (org_id, doc_kind) DO UPDATE SET min_legal_level = excluded.min_legal_level,"
              " min_identity_level = excluded.min_identity_level, require_timestamp = excluded.require_timestamp,"
              " note = excluded.note", ctx.org_id, d["doc_kind"], d["min_legal_level"], d["min_identity_level"],
              d["require_timestamp"], d["note"], ctx.user_id)
        ctx.audit(c, "signature_policy.set", "signature_policy", d["doc_kind"], d)
    return {"doc_kind": d["doc_kind"], "min_legal_level": d["min_legal_level"]}


# ------------------------------------------------------------------------------------------------ administração
def A(method, path, **kw):
    return route(method, path, auth="admin", tags=TA, **kw)


@A("GET", "/v1/admin/encryption/keys", summary="Inventário de chaves por impressão digital (a chave nunca é gravada)")
def key_inventory(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        out = KEYS.inventory(c)
    out["rotatable_tables"] = sorted(KEYS.ENCRYPTED_COLUMNS)
    out["purposes"] = list(KEYS.PURPOSES)
    return out


@A("POST", "/v1/admin/encryption/keys", body=C.KeyRegisterIn, status=201,
   summary="Registra no inventário as chaves em uso para uma finalidade")
def key_register(ctx: Ctx, body: C.KeyRegisterIn):
    provider = KEYS.EnvKeyProvider(ctx.settings)
    with ctx.tx() as c:
        out = KEYS.register(c, provider, purpose=body.purpose, note=body.note)
        ctx.audit(c, "encryption.key_registered", "encryption_key", body.purpose,
                  {"provider": provider.name, "active_fingerprint": out.get("active_fingerprint")})
    return out


@A("POST", "/v1/admin/encryption/reencrypt", body=C.ReencryptIn,
   summary="Recifra a coluna com a chave corrente (idempotente, com auditoria do resultado)")
def key_reencrypt(ctx: Ctx, body: C.ReencryptIn):
    with ctx.tx() as c:
        out = KEYS.reencrypt(c, ctx.app.cipher, table=body.table, actor_user_id=ctx.user_id)
        ctx.audit(c, "encryption.reencrypted", "encryption_rotation", out["rotation_id"],
                  {"table": out["table"], "rows": out["rows_reencrypted"], "failed": out["rows_failed"]})
    return out


@A("PUT", "/v1/admin/signature-providers/{provider_key}", body=C.ProviderUpdateIn,
   summary="Ajusta o estado real de um provedor de assinatura (passar para produção exige dependência resolvida)")
def update_provider(ctx: Ctx, body: C.ProviderUpdateIn):
    key = ctx.path["provider_key"]
    d = body.model_dump(exclude_none=True)
    if not d:
        raise ApiError(422, "validation_error", "Nada para atualizar")
    with ctx.tx() as c:
        p = c.one("SELECT key, legal_level, crypto_level, state, external_dependency FROM signature_providers"
                  " WHERE key = $1", key)
        if not p:
            raise not_found("Provedor de assinatura")
        if d.get("state") == "production" and p["legal_level"] == "qualified" \
                and p["crypto_level"] not in ("asymmetric_pkcs7", "asymmetric_pades"):
            raise ApiError(409, "cannot_promote",
                           "Um provedor de nível qualificado só vai a produção com assinatura assimétrica real "
                           "(certificado ICP-Brasil). Marcar como produção sem isso seria declarar validade que a "
                           "plataforma não entrega.")
        c.run("UPDATE signature_providers SET state = coalesce($2, state),"
              " activation_note = coalesce($3, activation_note), health_state = coalesce($4, health_state),"
              " health_detail = coalesce($5, health_detail),"
              " last_health_at = CASE WHEN $4::text IS NOT NULL THEN now() ELSE last_health_at END WHERE key = $1",
              key, d.get("state"), d.get("activation_note"), d.get("health_state"), d.get("health_detail"))
        ctx.audit(c, "signature_provider.updated", "signature_provider", key, d)
    return {"key": key, **d}


@A("GET", "/v1/admin/match/calibration", summary="Base para calibração futura do match (sem dado pessoal)")
def match_calibration(ctx: Ctx):
    from ..services import matching
    with ctx.tx(readonly=True) as c:
        return matching.calibration_dataset(c)
