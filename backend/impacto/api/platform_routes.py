"""Taxonomia (ODS/ESG/determinantes), idioma e tema, financiamento em cotas e campanha, honorários, catálogo de
serviços profissionais, georreferência e diagnóstico guiado.

Honestidade embutida nestas rotas:
* nenhum preço é inventado: publicar tabela de honorários exige nome da fonte, URL e data (CHECK no banco);
* os logos/emblemas oficiais da ONU **não** são distribuídos — a API devolve código, nome e cor oficial (ver SDG_ESG_TAXONOMY.md);
* a cobertura de tradução é declarada por idioma, em vez de prometer plataforma inteira traduzida;
* a localização de organização só é pública com consentimento registrado.
"""
from __future__ import annotations

from ..db.pq import Json
from ..http import ApiError, Ctx, not_found, page, route
from ..core import glossary as GLOSSARY
from . import trust_schemas as TSch

T = ("platform",)
WRITE = "manager"
OWNER = "owner"


# ================================================================================ taxonomia
@route("GET", "/v1/impact-taxonomy", min_role="viewer", tags=T,
       summary="Catálogo ODS (17), pilares ESG e determinantes sociais, com código, nome e cor oficial")
def taxonomy(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        # ods_goals é a tabela CONSOLIDADA (existia desde a 0001 e é referenciada por indicator_catalog);
        # a sdg_goals que eu havia criado na 0012 era duplicata e foi removida na 0013.
        sdg = c.query("SELECT number, code, name AS name_pt, name_en, color_hex FROM ods_goals"
                      " WHERE active ORDER BY number")
        esg = c.query("SELECT code, name_pt, name_en, description FROM esg_pillars ORDER BY code")
        det = c.query("SELECT code, name_pt, layer, description, source_note FROM social_determinants WHERE active ORDER BY code")
    return {"sdg": sdg, "esg": esg, "determinants": det,
            "notes": {"sdg": "Códigos, nomes e cores da Agenda 2030 da ONU. Os EMBLEMAS e o selo dos ODS são marcas "
                             "protegidas e não são distribuídos com a plataforma: para usá-los, siga as diretrizes da ONU.",
                      "determinants": "Lista editorial baseada no modelo de Dahlgren e Whitehead adotado pela CNDSS; "
                                      "redação da plataforma, revisão técnica pendente."}}


@route("POST", "/v1/impact-tags", body=TSch.TagIn, min_role=WRITE, status=201, tags=T,
       summary="Marca um objeto (projeto, solução, diagnóstico, necessidade…) com ODS, pilar ESG ou determinante social")
def tag_create(ctx: Ctx, body: TSch.TagIn):
    with ctx.tx() as c:
        tid = c.scalar("INSERT INTO impact_tags(org_id, subject_type, subject_id, taxonomy, code, is_primary, note, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (subject_type, subject_id, taxonomy, code)"
                       " DO UPDATE SET is_primary = $6, note = $7 RETURNING id::text",
                       ctx.org_id, body.subject_type, body.subject_id, body.taxonomy, body.code, body.is_primary,
                       body.note, ctx.user_id)
        ctx.audit(c, "impact_tag.set", body.subject_type, body.subject_id, {"taxonomy": body.taxonomy, "code": body.code})
    return {"id": tid}


@route("GET", "/v1/impact-tags", query=TSch.TagQ, min_role="viewer", tags=T, summary="Marcadores de um objeto")
def tag_list(ctx: Ctx, q: TSch.TagQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT t.id::text AS id, t.taxonomy, t.code, t.is_primary, t.note,"
                       " coalesce(g.name, p.name_pt, d.name_pt) AS name, g.color_hex"
                       " FROM impact_tags t LEFT JOIN ods_goals g ON t.taxonomy = 'sdg' AND g.code = t.code"
                       " LEFT JOIN esg_pillars p ON t.taxonomy = 'esg' AND p.code = t.code"
                       " LEFT JOIN social_determinants d ON t.taxonomy = 'determinant' AND d.code = t.code"
                       " WHERE t.subject_type = $1 AND t.subject_id = $2 ORDER BY t.taxonomy, t.code",
                       q.subject_type, q.subject_id)
    return {"items": rows}


@route("DELETE", "/v1/impact-tags/{tag_id}", min_role=WRITE, status=204, tags=T, summary="Remove um marcador")
def tag_delete(ctx: Ctx):
    with ctx.tx() as c:
        if not c.scalar("DELETE FROM impact_tags WHERE id = $1 AND org_id = $2 RETURNING 1", ctx.path["tag_id"], ctx.org_id):
            raise not_found("Marcador")
    return None


# ================================================================================ idioma e tema
@route("GET", "/v1/public/locales", auth="none", rate=("locales_ip", 120, 3600), tags=("public",),
       summary="Idiomas disponíveis, com a cobertura real de tradução declarada")
def locales(ctx: Ctx):
    with ctx.system_tx() as c:
        rows = c.query("SELECT code, name_pt, native_name, is_default, coverage_note FROM locales WHERE active ORDER BY"
                       " is_default DESC, code")
    return {"items": rows, "note": "pt-BR é o idioma de origem. Nos outros, o que não estiver traduzido aparece em português."}


@route("GET", "/v1/public/translations", auth="none", query=TSch.TranslationsQ, rate=("tr_ip", 240, 3600), tags=("public",),
       summary="Catálogo de traduções do idioma (chaves ausentes devem cair para pt-BR no cliente)")
def translations(ctx: Ctx, q: TSch.TranslationsQ):
    with ctx.system_tx() as c:
        if q.namespace:
            rows = c.query("SELECT namespace, key, value FROM translations WHERE locale = $1 AND namespace = $2",
                           q.locale, q.namespace)
        else:
            rows = c.query("SELECT namespace, key, value FROM translations WHERE locale = $1", q.locale)
        known = c.scalar("SELECT 1 FROM locales WHERE code = $1 AND active", q.locale)
    if not known:
        raise not_found("Idioma")
    catalog: dict[str, dict[str, str]] = {}
    for r in rows:
        catalog.setdefault(r["namespace"], {})[r["key"]] = r["value"]
    return {"locale": q.locale, "catalog": catalog, "keys": sum(len(v) for v in catalog.values())}


@route("GET", "/v1/public/glossary", auth="none", query=TSch.GlossaryQ, rate=("gloss_ip", 120, 3600),
       tags=("public",),
       summary="Vocabulário oficial: termo da API, rótulo de tela e definição (origem: config/glossary.json)")
def glossary(ctx: Ctx, q: TSch.GlossaryQ):
    """Uma palavra por conceito, em todas as camadas.

    Esta rota existe para que a interface NÃO invente sinônimo: o rótulo que a tela mostra sai daqui, e o
    teste `test_v0190_glossary` reprova quando um valor novo de enum aparece no código sem entrada no
    glossário. A definição vem sempre em pt-BR: ela é para quem desenha e para quem escreve texto de ajuda,
    não é texto de tela.
    """
    doc = GLOSSARY.catalog(q.locale)
    if q.domain:
        doc["domains"] = [d for d in doc["domains"] if d["key"] == q.domain]
        if not doc["domains"]:
            raise not_found("Domínio do glossário")
    return doc


@route("GET", "/v1/me/preferences", auth="user", tags=T, summary="Idioma e tema da pessoa (tema: system, light ou dark)")
def prefs_get(ctx: Ctx):
    with ctx.system_tx() as c:
        row = c.one("SELECT locale, theme, prefs_set_at FROM users WHERE id = $1", ctx.user_id)
    return {**row, "asked": row["prefs_set_at"] is not None}


@route("PUT", "/v1/me/preferences", auth="user", body=TSch.PrefsIn, tags=T,
       summary="Define idioma e tema (a interface pergunta uma vez, logo depois do primeiro acesso)")
def prefs_put(ctx: Ctx, body: TSch.PrefsIn):
    if body.locale is None and body.theme is None:
        raise ApiError(422, "validation_error", "Informe idioma e/ou tema")
    with ctx.system_tx() as c:
        if body.locale and not c.scalar("SELECT 1 FROM locales WHERE code = $1 AND active", body.locale):
            raise ApiError(422, "unknown_locale", "Idioma não disponível")
        c.run("UPDATE users SET locale = coalesce($2, locale), theme = coalesce($3, theme), prefs_set_at = now()"
              " WHERE id = $1", ctx.user_id, body.locale, body.theme)
        row = c.one("SELECT locale, theme FROM users WHERE id = $1", ctx.user_id)
    with ctx.tx() as c:
        ctx.audit(c, "prefs.updated", "user", ctx.user_id, {"locale": row["locale"], "theme": row["theme"]})
    return row


# ================================================================================ financiamento em cotas
def _quota_view(c, quota_id: str) -> dict:
    """ATENÇÃO: a soma das reservas precisa de visão completa. Chame em contexto de sistema (ou sendo a dona da cota),
    senão a RLS esconde as reservas de outras organizações e "cotas restantes" sai errado para quem apoia."""
    q = c.one("SELECT id::text AS id, project_id::text AS project_id, org_id::text AS org_id, label, description,"
              " quota_cents, total_quotas, min_per_backer, max_per_backer, status, deadline, created_at"
              " FROM funding_quotas WHERE id = $1", quota_id)
    if not q:
        return {}
    taken = c.one("SELECT coalesce(sum(quantity) FILTER (WHERE status IN ('pledged','confirmed')), 0) AS taken,"
                  " coalesce(sum(quantity) FILTER (WHERE status = 'confirmed'), 0) AS confirmed,"
                  " coalesce(sum(amount_cents) FILTER (WHERE status = 'confirmed'), 0) AS raised_cents,"
                  " count(*) FILTER (WHERE status IN ('pledged','confirmed')) AS backers"
                  " FROM quota_pledges WHERE quota_id = $1", quota_id)
    q.update(taken)
    q["remaining_quotas"] = q["total_quotas"] - q["taken"]
    q["goal_cents"] = q["total_quotas"] * q["quota_cents"]
    return q


@route("POST", "/v1/funding-quotas", body=TSch.QuotaIn, min_role=WRITE, status=201, tags=("funding",),
       summary="Cria cotas de financiamento para um projeto (o valor da cota é definido pela organização proponente)")
def quota_create(ctx: Ctx, body: TSch.QuotaIn):
    with ctx.tx() as c:
        if not c.scalar("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", body.project_id, ctx.org_id):
            raise not_found("Projeto")
        qid = c.scalar("INSERT INTO funding_quotas(project_id, org_id, label, description, quota_cents, total_quotas,"
                       " min_per_backer, max_per_backer, deadline, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::date,$10) RETURNING id::text",
                       body.project_id, ctx.org_id, body.label, body.description, body.quota_cents, body.total_quotas,
                       body.min_per_backer, body.max_per_backer, body.deadline, ctx.user_id)
        ctx.audit(c, "quota.created", "funding_quota", qid, {"total": body.total_quotas, "cents": body.quota_cents})
    return {"id": qid, "status": "draft", "next": "Abra as cotas quando o projeto estiver pronto para receber apoio."}


@route("GET", "/v1/funding-quotas", query=TSch.Pagination, min_role="viewer", tags=("funding",),
       summary="Cotas da organização, com quantas faltam")
def quota_list(ctx: Ctx, q: TSch.Pagination):
    with ctx.tx(readonly=True) as c:
        ids = c.query("SELECT id::text AS id FROM funding_quotas WHERE org_id = $1 ORDER BY created_at DESC"
                      " LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
        rows = [_quota_view(c, r["id"]) for r in ids]
    return page(rows, q.limit, q.offset)


@route("PATCH", "/v1/funding-quotas/{quota_id}", body=TSch.QuotaPatch, min_role=WRITE, tags=("funding",),
       summary="Abre, pausa ou fecha as cotas e ajusta rótulo/prazo (quantidade e valor não mudam depois de criados)")
def quota_patch(ctx: Ctx, body: TSch.QuotaPatch):
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not fields:
        raise ApiError(422, "validation_error", "Nada para alterar")
    with ctx.tx() as c:
        if not c.scalar("SELECT 1 FROM funding_quotas WHERE id = $1 AND org_id = $2", ctx.path["quota_id"], ctx.org_id):
            raise not_found("Cota")
        sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(fields))
        c.run(f"UPDATE funding_quotas SET {sets} WHERE id = $1", ctx.path["quota_id"], *fields.values())
        ctx.audit(c, "quota.updated", "funding_quota", ctx.path["quota_id"], {"fields": sorted(fields)})
        return _quota_view(c, ctx.path["quota_id"])


@route("POST", "/v1/funding-quotas/{quota_id}/pledges", body=TSch.PledgeIn, min_role="member", status=201,
       rate=("pledge_ip", 60, 3600), tags=("funding",),
       summary="Reserva cotas (o banco impede vender mais do que existe, inclusive com pedidos simultâneos)")
def pledge_create(ctx: Ctx, body: TSch.PledgeIn):
    with ctx.tx() as c:
        q = c.one("SELECT id::text AS id, project_id::text AS project_id, org_id::text AS org_id, quota_cents, status"
                  " FROM funding_quotas WHERE id = $1", ctx.path["quota_id"])
        if not q:
            raise not_found("Cota")
        if q["org_id"] == ctx.org_id:
            raise ApiError(409, "own_project", "A organização proponente não apoia o próprio projeto")
        if q["status"] != "open":
            raise ApiError(409, "not_open", "Estas cotas não estão abertas para apoio")
        pid = c.scalar("INSERT INTO quota_pledges(quota_id, project_id, backer_org_id, backer_user_id, quantity,"
                       " amount_cents, display_name, is_anonymous, note) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)"
                       " RETURNING id::text", q["id"], q["project_id"], ctx.org_id, ctx.user_id, body.quantity,
                       body.quantity * q["quota_cents"], body.display_name, body.is_anonymous, body.note)
        ctx.audit(c, "quota.pledged", "funding_quota", q["id"], {"quantity": body.quantity})
    with ctx.system_tx() as c:
        view = _quota_view(c, q["id"])
    return {"id": pid, "status": "pledged", "amount_cents": body.quantity * q["quota_cents"],
            "remaining_quotas": view["remaining_quotas"],
            "note": "Reserva registrada. A confirmação depende do pagamento, que é registrado pela equipe — a plataforma "
                    "não processa pagamento desta reserva automaticamente."}


@route("GET", "/v1/funding-quotas/{quota_id}/pledges", query=TSch.Pagination, min_role="viewer", tags=("funding",),
       summary="Apoios de uma cota (proponente vê todos; apoiadora vê os seus)")
def pledge_list(ctx: Ctx, q: TSch.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT p.id::text AS id, p.quantity, p.amount_cents, p.status, p.is_anonymous, p.display_name,"
                       " p.created_at, p.backer_org_id::text AS backer_org_id, o.legal_name AS backer_name"
                       " FROM quota_pledges p LEFT JOIN organizations o ON o.id = p.backer_org_id"
                       " WHERE p.quota_id = $1 ORDER BY p.created_at DESC LIMIT $2 OFFSET $3",
                       ctx.path["quota_id"], q.limit + 1, q.offset)
    for r in rows:
        if r["is_anonymous"]:
            r["backer_name"] = r["display_name"] or "Apoiador anônimo"
            r["backer_org_id"] = None
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/admin/funding-quotas/pledges/{pledge_id}/confirm", auth="admin", body=TSch.RevokeIn,
       tags=("admin", "funding"), summary="Confirma o recebimento de um apoio (registro humano; a reserva não se confirma sozinha)")
def pledge_confirm(ctx: Ctx, body: TSch.RevokeIn):
    with ctx.system_tx() as c:
        p = c.one("SELECT id::text AS id, quota_id::text AS quota_id, status FROM quota_pledges WHERE id = $1",
                  ctx.path["pledge_id"])
        if not p:
            raise not_found("Apoio")
        if p["status"] != "pledged":
            raise ApiError(409, "not_pledged", "Somente uma reserva pendente pode ser confirmada")
        c.run("UPDATE quota_pledges SET status = 'confirmed', payment_ref = $2 WHERE id = $1", p["id"], body.reason[:200])
    with ctx.tx() as c:
        ctx.audit(c, "quota.confirmed", "quota_pledge", p["id"], {})
    return {"confirmed": True, "pledge_id": p["id"]}


# ================================================================================ campanha pública
@route("POST", "/v1/campaigns", body=TSch.CampaignIn, min_role=WRITE, status=201, tags=("funding",),
       summary="Cria a campanha de divulgação do projeto (rascunho; publicar é um passo separado)")
def campaign_create(ctx: Ctx, body: TSch.CampaignIn):
    with ctx.tx(readonly=True) as c:
        if not c.scalar("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", body.project_id, ctx.org_id):
            raise not_found("Projeto")
    with ctx.system_tx() as c:          # slug é namespace global: a checagem não pode depender da RLS
        if c.scalar("SELECT 1 FROM campaigns WHERE slug = $1", body.slug):
            raise ApiError(409, "slug_taken", "Este endereço de campanha já está em uso")
    with ctx.tx() as c:
        if c.scalar("SELECT 1 FROM campaigns WHERE project_id = $1", body.project_id):
            raise ApiError(409, "campaign_exists", "Este projeto já tem campanha")
        cid = c.scalar("INSERT INTO campaigns(project_id, org_id, slug, title, summary, story, cover_document_id,"
                       " show_backers, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id::text",
                       body.project_id, ctx.org_id, body.slug, body.title, body.summary, body.story,
                       body.cover_document_id, body.show_backers, ctx.user_id)
        ctx.audit(c, "campaign.created", "campaign", cid, {"slug": body.slug})
    return {"id": cid, "slug": body.slug, "status": "draft", "public_path": f"/campanha/{body.slug}"}


@route("GET", "/v1/campaigns", query=TSch.Pagination, min_role="viewer", tags=("funding",),
       summary="Campanhas da organização, com o endereço público e a situação")
def campaign_list(ctx: Ctx, q: TSch.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT c.id::text AS id, c.slug, c.title, c.summary, c.status, c.show_backers, c.published_at,"
                       " c.project_id::text AS project_id, p.title AS project_title FROM campaigns c"
                       " JOIN projects p ON p.id = c.project_id WHERE c.org_id = $1 ORDER BY c.created_at DESC"
                       " LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    for r in rows[:q.limit]:
        r["public_path"] = f"/campanha/{r['slug']}"
    return page(rows, q.limit, q.offset)


@route("PATCH", "/v1/campaigns/{campaign_id}", body=TSch.CampaignPatch, min_role=WRITE, tags=("funding",),
       summary="Altera ou publica/fecha a campanha")
def campaign_patch(ctx: Ctx, body: TSch.CampaignPatch):
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not fields:
        raise ApiError(422, "validation_error", "Nada para alterar")
    status = fields.pop("status", None)
    with ctx.tx() as c:
        if not c.scalar("SELECT 1 FROM campaigns WHERE id = $1 AND org_id = $2", ctx.path["campaign_id"], ctx.org_id):
            raise not_found("Campanha")
        if fields:
            sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(fields))
            c.run(f"UPDATE campaigns SET {sets} WHERE id = $1", ctx.path["campaign_id"], *fields.values())
        if status == "published":
            c.run("UPDATE campaigns SET status = 'published', published_at = coalesce(published_at, now()) WHERE id = $1",
                  ctx.path["campaign_id"])
        elif status == "closed":
            c.run("UPDATE campaigns SET status = 'closed', closed_at = now() WHERE id = $1", ctx.path["campaign_id"])
        elif status == "draft":
            c.run("UPDATE campaigns SET status = 'draft' WHERE id = $1", ctx.path["campaign_id"])
        ctx.audit(c, "campaign.updated", "campaign", ctx.path["campaign_id"], {"status": status})
    return {"updated": True, "status": status}


@route("GET", "/v1/public/campaigns/{slug}", auth="none", rate=("camp_ip", 120, 3600), tags=("public",),
       summary="Campanha pública: história do projeto, meta e QUANTAS COTAS FALTAM")
def campaign_public(ctx: Ctx):
    with ctx.system_tx() as c:
        camp = c.one("SELECT c.id::text AS id, c.slug, c.title, c.summary, c.story, c.status, c.published_at,"
                     " c.show_backers, c.cover_document_id::text AS cover_document_id, c.project_id::text AS project_id,"
                     " p.title AS project_title, o.legal_name, o.trade_name, o.city, o.uf, o.kind"
                     " FROM campaigns c JOIN projects p ON p.id = c.project_id JOIN organizations o ON o.id = c.org_id"
                     " WHERE c.slug = $1 AND c.status = 'published'", ctx.path["slug"])
        if not camp:
            raise not_found("Campanha")
        quotas = [_quota_view(c, r["id"]) for r in
                  c.query("SELECT id::text AS id FROM funding_quotas WHERE project_id = $1 AND status IN ('open','closed')"
                          " ORDER BY created_at", camp["project_id"])]
        backers = []
        if camp["show_backers"]:
            backers = c.query("SELECT CASE WHEN p.is_anonymous THEN coalesce(p.display_name, 'Apoiador anônimo')"
                              " ELSE coalesce(p.display_name, o.trade_name, o.legal_name) END AS name, p.quantity,"
                              " p.created_at FROM quota_pledges p LEFT JOIN organizations o ON o.id = p.backer_org_id"
                              " WHERE p.project_id = $1 AND p.status = 'confirmed' ORDER BY p.created_at DESC LIMIT 50",
                              camp["project_id"])
        tags = c.query("SELECT t.taxonomy, t.code, coalesce(g.name, pl.name_pt, d.name_pt) AS name, g.color_hex"
                       " FROM impact_tags t LEFT JOIN ods_goals g ON t.taxonomy = 'sdg' AND g.code = t.code"
                       " LEFT JOIN esg_pillars pl ON t.taxonomy = 'esg' AND pl.code = t.code"
                       " LEFT JOIN social_determinants d ON t.taxonomy = 'determinant' AND d.code = t.code"
                       " WHERE t.subject_type = 'project' AND t.subject_id = $1", camp["project_id"])
    total_remaining = sum(q["remaining_quotas"] for q in quotas)
    return {"campaign": {k: camp[k] for k in ("slug", "title", "summary", "story", "published_at", "project_title")},
            "organization": {"name": camp["trade_name"] or camp["legal_name"], "city": camp["city"], "uf": camp["uf"],
                             "kind": camp["kind"]},
            "quotas": quotas, "remaining_quotas": total_remaining, "impact_tags": tags, "backers": backers,
            "note": "Reservas de cota são registradas na plataforma; a confirmação depende do repasse combinado com a "
                    "organização proponente."}


# ================================================================================ honorários
@route("GET", "/v1/fee-tables", query=TSch.Pagination, min_role="viewer", tags=("professional",),
       summary="Tabelas de honorários publicadas, com a fonte e a data de consulta (a plataforma não inventa valor)")
def fee_tables(ctx: Ctx, q: TSch.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT t.id::text AS id, t.council_code, t.title, t.version, t.reference_year, t.source_name,"
                       " t.source_url, t.source_date, t.notes, t.published_at, cl.name AS council_name,"
                       " (SELECT count(*) FROM fee_items i WHERE i.fee_table_id = t.id) AS items"
                       " FROM fee_tables t JOIN professional_councils cl ON cl.code = t.council_code"
                       " WHERE t.status = 'published' ORDER BY t.council_code, t.version LIMIT $1 OFFSET $2",
                       q.limit + 1, q.offset)
    out = page(rows, q.limit, q.offset)
    out["note"] = ("Valores de referência vêm das tabelas publicadas pelos conselhos. Enquanto nenhuma tabela for "
                   "cadastrada com fonte e data, esta lista fica vazia — a plataforma não estima honorário.")
    return out


@route("GET", "/v1/fee-tables/{table_id}", min_role="viewer", tags=("professional",), summary="Itens de uma tabela de honorários")
def fee_table_detail(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        t = c.one("SELECT id::text AS id, council_code, title, version, reference_year, source_name, source_url,"
                  " source_date, notes, status FROM fee_tables WHERE id = $1", ctx.path["table_id"])
        if not t:
            raise not_found("Tabela")
        t["items"] = c.query("SELECT id::text AS id, service_code, description, unit, reference_cents, min_cents,"
                             " max_cents, negotiable, note FROM fee_items WHERE fee_table_id = $1 ORDER BY service_code",
                             t["id"])
    return t


@route("POST", "/v1/admin/fee-tables", auth="admin", body=TSch.FeeTableIn, status=201, tags=("admin", "professional"),
       summary="Cria tabela de honorários em rascunho (publicar exige fonte, URL e data de consulta)")
def fee_table_create(ctx: Ctx, body: TSch.FeeTableIn):
    with ctx.system_tx() as c:
        if not c.scalar("SELECT 1 FROM professional_councils WHERE code = $1", body.council_code):
            raise ApiError(422, "unknown_council", "Conselho não está no catálogo")
        if c.scalar("SELECT 1 FROM fee_tables WHERE council_code = $1 AND version = $2", body.council_code, body.version):
            raise ApiError(409, "duplicate_version", "Já existe esta versão para este conselho")
        tid = c.scalar("INSERT INTO fee_tables(council_code, title, version, reference_year, source_name, source_url,"
                       " source_date, notes) VALUES ($1,$2,$3,$4,$5,$6,$7::date,$8) RETURNING id::text",
                       body.council_code, body.title, body.version, body.reference_year, body.source_name,
                       body.source_url, body.source_date, body.notes)
    with ctx.tx() as c:
        ctx.audit(c, "fee_table.created", "fee_table", tid, {"council": body.council_code})
    return {"id": tid, "status": "draft"}


@route("POST", "/v1/admin/fee-tables/{table_id}/items", auth="admin", body=TSch.FeeItemIn, status=201,
       tags=("admin", "professional"), summary="Acrescenta item à tabela de honorários (valor vem da fonte, não da plataforma)")
def fee_item_create(ctx: Ctx, body: TSch.FeeItemIn):
    with ctx.system_tx() as c:
        t = c.one("SELECT id::text AS id, status FROM fee_tables WHERE id = $1", ctx.path["table_id"])
        if not t:
            raise not_found("Tabela")
        if t["status"] != "draft":
            raise ApiError(409, "not_draft", "Tabela publicada não é editada: crie uma nova versão")
        iid = c.scalar("INSERT INTO fee_items(fee_table_id, service_code, description, unit, reference_cents, min_cents,"
                       " max_cents, negotiable, note) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id::text",
                       t["id"], body.service_code, body.description, body.unit, body.reference_cents, body.min_cents,
                       body.max_cents, body.negotiable, body.note)
    return {"id": iid}


@route("POST", "/v1/admin/fee-tables/{table_id}/publish", auth="admin", tags=("admin", "professional"),
       summary="Publica a tabela (recusado sem nome da fonte, URL e data de consulta)")
def fee_table_publish(ctx: Ctx):
    with ctx.system_tx() as c:
        t = c.one("SELECT id::text AS id, status, source_name, source_url, source_date FROM fee_tables WHERE id = $1",
                  ctx.path["table_id"])
        if not t:
            raise not_found("Tabela")
        if t["status"] != "draft":
            raise ApiError(409, "not_draft", "Somente rascunho é publicado")
        if not (t["source_name"] and t["source_url"] and t["source_date"]):
            raise ApiError(422, "source_required", "Para publicar é obrigatório informar nome da fonte, URL (https) e data de consulta")
        c.run("UPDATE fee_tables SET status = 'published', published_by = $2, published_at = now() WHERE id = $1",
              t["id"], ctx.user_id)
    with ctx.tx() as c:
        ctx.audit(c, "fee_table.published", "fee_table", t["id"], {})
    return {"published": True, "id": t["id"]}


# ================================================================================ catálogo de serviços profissionais
@route("POST", "/v1/professional-services", body=TSch.ServiceIn, kinds=("provider", "individual"), min_role=WRITE,
       status=201, tags=("professional",), summary="Cadastra uma atividade oferecida (preço é da profissional, com margem de negociação)")
def service_create(ctx: Ctx, body: TSch.ServiceIn):
    with ctx.tx() as c:
        if body.credential_id and not c.scalar("SELECT 1 FROM professional_credentials WHERE id = $1 AND org_id = $2",
                                               body.credential_id, ctx.org_id):
            raise ApiError(422, "unknown_credential", "Credencial não encontrada nesta organização")
        sid = c.scalar("INSERT INTO professional_services(org_id, user_id, credential_id, fee_item_id, title, description,"
                       " modality, unit, price_cents, negotiable, duration_min) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)"
                       " RETURNING id::text", ctx.org_id, ctx.user_id, body.credential_id, body.fee_item_id, body.title,
                       body.description, body.modality, body.unit, body.price_cents, body.negotiable, body.duration_min)
        ctx.audit(c, "service.created", "professional_service", sid, {})
    return {"id": sid, "status": "draft"}


@route("GET", "/v1/professional-services", query=TSch.Pagination, min_role="viewer", tags=("professional",),
       summary="Atividades cadastradas pela organização")
def service_list(ctx: Ctx, q: TSch.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT s.id::text AS id, s.title, s.description, s.modality, s.unit, s.price_cents, s.negotiable,"
                       " s.duration_min, s.status, s.created_at, c.council, c.number, c.uf, c.verification_status"
                       " FROM professional_services s LEFT JOIN professional_credentials c ON c.id = s.credential_id"
                       " WHERE s.org_id = $1 ORDER BY s.created_at DESC LIMIT $2 OFFSET $3",
                       ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("PATCH", "/v1/professional-services/{service_id}", body=TSch.ServicePatch, min_role=WRITE, tags=("professional",),
       summary="Altera ou publica uma atividade")
def service_patch(ctx: Ctx, body: TSch.ServicePatch):
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not fields:
        raise ApiError(422, "validation_error", "Nada para alterar")
    with ctx.tx() as c:
        if not c.scalar("SELECT 1 FROM professional_services WHERE id = $1 AND org_id = $2", ctx.path["service_id"], ctx.org_id):
            raise not_found("Atividade")
        sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(fields))
        c.run(f"UPDATE professional_services SET {sets} WHERE id = $1", ctx.path["service_id"], *fields.values())
        ctx.audit(c, "service.updated", "professional_service", ctx.path["service_id"], {"fields": sorted(fields)})
    return {"updated": True}


@route("GET", "/v1/directory/services", query=TSch.DirectoryQ, min_role="viewer", tags=("professional",),
       summary="Busca por ATIVIDADE oferecida, com card completo: preço, credencial verificada, ODS e localização (quando pública)."
               " O diretório por organização continua em GET /v1/directory/professionals.")
def directory_services(ctx: Ctx, q: TSch.DirectoryQ):
    where = ["s.status = 'published'", "o.status = 'active'"]
    args: list = []
    if q.q:
        args.append(f"%{q.q}%")
        where.append(f"(s.title ILIKE ${len(args)} OR o.legal_name ILIKE ${len(args)} OR o.trade_name ILIKE ${len(args)})")
    if q.uf:
        args.append(q.uf)
        where.append(f"o.uf = ${len(args)}")
    if q.council:
        args.append(q.council)
        where.append(f"c.council = ${len(args)}")
    if q.sdg:
        args.append(q.sdg)
        where.append(f"EXISTS (SELECT 1 FROM impact_tags t WHERE t.subject_type = 'organization'"
                     f" AND t.subject_id = o.id AND t.taxonomy = 'sdg' AND t.code = ${len(args)})")
    args += [q.limit + 1, q.offset]
    with ctx.system_tx() as c:
        rows = c.query(
            "SELECT s.id::text AS id, s.title, s.description, s.modality, s.unit, s.price_cents, s.negotiable,"
            " s.duration_min, o.id::text AS org_id, coalesce(o.trade_name, o.legal_name) AS org_name, o.city, o.uf,"
            " o.description AS org_description, o.website,"
            " CASE WHEN o.geo_public THEN o.lat END AS lat, CASE WHEN o.geo_public THEN o.lng END AS lng,"
            " CASE WHEN o.geo_public THEN o.geo_precision END AS geo_precision,"
            " c.council, c.number AS council_number, c.uf AS council_uf, c.verification_status,"
            " (SELECT array_agg(t.code ORDER BY t.code) FROM impact_tags t WHERE t.subject_type = 'organization'"
            "  AND t.subject_id = o.id AND t.taxonomy = 'sdg') AS sdg"
            " FROM professional_services s JOIN organizations o ON o.id = s.org_id"
            " LEFT JOIN professional_credentials c ON c.id = s.credential_id"
            f" WHERE {' AND '.join(where)} ORDER BY (c.verification_status = 'verified') DESC, s.created_at DESC"
            f" LIMIT ${len(args) - 1} OFFSET ${len(args)}", *args)
    out = page(rows, q.limit, q.offset)
    out["note"] = ("Credencial 'verificada' significa documento conferido pela equipe, não consulta ao conselho. "
                   "Localização aparece apenas quando a organização autorizou a divulgação.")
    return out


# ================================================================================ georreferência
@route("PUT", "/v1/org/geo", body=TSch.GeoIn, min_role=OWNER, tags=T,
       summary="Define a localização da organização; tornar pública exige consentimento explícito (registrado com data)")
def org_geo(ctx: Ctx, body: TSch.GeoIn):
    with ctx.tx() as c:
        c.run("UPDATE organizations SET lat = $2, lng = $3, geo_precision = $4, geo_public = $5,"
              " geo_consent_at = CASE WHEN $5 THEN coalesce(geo_consent_at, now()) ELSE NULL END WHERE id = $1",
              ctx.org_id, body.lat, body.lng, body.precision, body.public)
        ctx.audit(c, "org.geo_updated", "organization", ctx.org_id, {"public": body.public, "precision": body.precision})
    return {"updated": True, "public": body.public,
            "note": "Localização exata de pessoa física é dado pessoal: prefira precisão por cidade quando o endereço "
                    "for residencial."}


# ================================================================================ diagnóstico guiado
@route("GET", "/v1/diagnoses/{diagnosis_id}/guide", min_role="viewer", tags=("diagnoses",),
       summary="Roteiro guiado do diagnóstico: etapas, perguntas, documentos exigidos e progresso real")
def diagnosis_guide(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        if not c.scalar("SELECT 1 FROM diagnoses WHERE id = $1", ctx.path["diagnosis_id"]):
            raise not_found("Diagnóstico")
        stages = c.query("SELECT code, position, title, purpose, questions, required_documents, help_key"
                         " FROM diagnosis_stages WHERE active ORDER BY position")
        prog = {r["stage_code"]: r for r in c.query(
            "SELECT stage_code, status, answers, document_ids, skip_reason, completed_at, updated_at"
            " FROM diagnosis_progress WHERE diagnosis_id = $1", ctx.path["diagnosis_id"])}
    for s in stages:
        p = prog.get(s["code"])
        s["progress"] = p or {"status": "pending", "answers": {}, "document_ids": []}
    done = sum(1 for s in stages if s["progress"]["status"] in ("complete", "skipped"))
    nxt = next((s["code"] for s in stages if s["progress"]["status"] not in ("complete", "skipped")), None)
    return {"stages": stages, "completed_stages": done, "total_stages": len(stages),
            "percent": round(done * 100 / len(stages)) if stages else 0, "next_stage": nxt,
            "note": "As etapas são uma hipótese editorial da plataforma, não metodologia normatizada por órgão."}


@route("PUT", "/v1/diagnoses/{diagnosis_id}/guide/{stage_code}", body=TSch.StageIn, min_role=WRITE, tags=("diagnoses",),
       summary="Salva as respostas e os documentos de uma etapa do diagnóstico guiado")
def diagnosis_stage_put(ctx: Ctx, body: TSch.StageIn):
    with ctx.tx() as c:
        if not c.scalar("SELECT 1 FROM diagnoses WHERE id = $1 AND org_id = $2", ctx.path["diagnosis_id"], ctx.org_id):
            raise not_found("Diagnóstico")
        stage = c.one("SELECT code, questions, required_documents FROM diagnosis_stages WHERE code = $1 AND active",
                      ctx.path["stage_code"])
        if not stage:
            raise not_found("Etapa")
        missing: list[str] = []
        if body.complete and not body.skip_reason:
            for qq in stage["questions"]:
                if qq.get("required") and not body.answers.get(qq["key"]):
                    missing.append(qq["label"])
            needed = [d for d in stage["required_documents"] if d.get("required")]
            if needed and len(body.document_ids) < len(needed):
                missing += [d["label"] for d in needed]
        if missing:
            raise ApiError(422, "stage_incomplete", "Faltam informações obrigatórias: " + "; ".join(missing[:6]))
        for did in body.document_ids:
            if not c.scalar("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL", did, ctx.org_id):
                raise ApiError(422, "unknown_document", "Documento não encontrado nesta organização")
        status = "skipped" if body.skip_reason else ("complete" if body.complete else "in_progress")
        c.run("INSERT INTO diagnosis_progress(diagnosis_id, org_id, stage_code, status, answers, document_ids,"
              " skip_reason, updated_by, completed_at) VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8,"
              " CASE WHEN $4 IN ('complete','skipped') THEN now() END)"
              " ON CONFLICT (diagnosis_id, stage_code) DO UPDATE SET status = $4, answers = $5::jsonb,"
              " document_ids = $6, skip_reason = $7, updated_by = $8, updated_at = now(),"
              " completed_at = CASE WHEN $4 IN ('complete','skipped') THEN now() ELSE NULL END",
              ctx.path["diagnosis_id"], ctx.org_id, stage["code"], status, Json(body.answers),
              list(body.document_ids), body.skip_reason, ctx.user_id)
        ctx.audit(c, "diagnosis.stage_saved", "diagnosis", ctx.path["diagnosis_id"], {"stage": stage["code"], "status": status})
    return {"stage_code": stage["code"], "status": status}
