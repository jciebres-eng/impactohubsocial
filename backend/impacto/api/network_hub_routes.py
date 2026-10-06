"""Rotas da rede, parte 2: workspace, marketplace, relatório de impacto, perfil público, persona, taxonomia,
território, experiência profissional, recomendação, prontidão e eventos de domínio.

Duas rotas deste arquivo merecem atenção na revisão:

* ``GET /@{handle}`` (perfil público) roda em contexto de SISTEMA e lê exclusivamente `public_profiles.public_fields`.
  Contexto de sistema aqui não é atalho — é o que permite servir um perfil a quem não tem conta. A proteção não vem
  do contexto, vem de a coluna lida ser uma projeção curada: não há tabela privada nessa consulta.

* ``GET /v1/marketplace/feed`` é a ÚNICA leitura pública do marketplace, e `publication_state = 'published'` está
  escrito uma vez, dentro de `marketplace.public_feed()`. Nenhuma outra rota pública consulta projeto para listar —
  inclusive a seção "descobrir" de todos os workspaces passa por aqui.
"""
from __future__ import annotations

from ..http import ApiError, Ctx, forbidden, not_found, page, route, unprocessable
from ..network import enforcement as ENF
from ..network import events as EV
from ..network import impact_report as IR
from ..network import marketplace as MK
from ..network import profiles as PRO
from ..network import readiness as RD
from ..network import recommendation as RC
from ..network import workspace as WS
from . import network_schemas as N

TW = ("workspace",)
TM = ("marketplace",)
TI = ("impacto",)
TPF = ("perfil publico",)
TX = ("taxonomia",)
TT = ("territorio",)


# ================================================================================================ workspace
@route("GET", "/v1/workspace", query=N.WorkspaceQ, min_role="viewer", tags=TW,
       summary="WorkspaceContext: persona, capacidades, contadores, próximas ações e seções em ordem")
def workspace(ctx: Ctx, q: N.WorkspaceQ):
    p = ctx.principal
    with ctx.tx() as c:
        return WS.context(c, org_id=ctx.org_id, org_kind=p.org_kind or "osc", user_id=ctx.user_id,
                          role=p.role or "viewer", persona=q.persona, platform_admin=ctx.admin_mode)


@route("GET", "/v1/workspace/personas", auth="user", tags=TW,
       summary="Personas disponíveis (persona orienta o workspace; permissão continua vindo de papel e plano)")
def list_personas(ctx: Ctx):
    kind = ctx.principal.org_kind if ctx.principal else None
    with ctx.tx(readonly=True) as c:
        rows = WS.personas(c, org_kind=kind)
    return {"items": rows,
            "note": "Persona é declarada e pode ser mais de uma. Ela não concede permissão."}


@route("POST", "/v1/workspace/personas", body=N.PersonaIn, min_role="admin", status=201, tags=TW)
def declare_persona(ctx: Ctx, body: N.PersonaIn):
    with ctx.tx() as c:
        out = WS.declare(c, org_id=ctx.org_id, persona=body.persona, actor=ctx.user_id, primary=body.primary)
        ctx.audit(c, "persona.declared", "organization", ctx.org_id, out)
    return out


@route("DELETE", "/v1/workspace/personas/{persona}", min_role="admin", tags=TW)
def undeclare_persona(ctx: Ctx):
    with ctx.tx() as c:
        out = WS.undeclare(c, org_id=ctx.org_id, persona=ctx.path["persona"])
        # 404 quando não havia nada a remover. Responder 200 com "removidas: 0" seria dizer "deu certo" sobre uma
        # persona que a organização não tem — e a varredura de escrita (test_v0150_security) existe justamente para
        # impedir que uma rota responda com sucesso a um identificador que não é dela.
        if not out["removed"]:
            raise not_found("Persona declarada")
        ctx.audit(c, "persona.undeclared", "organization", ctx.org_id, {"persona": ctx.path["persona"]})
    return out


# ================================================================================================ prontidão
# NÃO é `/v1/readiness`: essa rota já existe desde a 0013 e responde outra pergunta — a completude e as lacunas do
# diagnóstico ("o que falta neste projeto?"). Esta responde "pronto PARA QUÊ?", em seis finalidades. Nomes diferentes
# para perguntas diferentes; juntar as duas numa rota só devolveria um número que ninguém saberia interpretar.
@route("GET", "/v1/readiness/purposes", query=N.ReadinessQ, min_role="viewer", tags=TW,
       summary="Prontidão por finalidade: seis números, cada um com os critérios que o compuseram")
def readiness(ctx: Ctx, q: N.ReadinessQ):
    with ctx.tx(readonly=True) as c:
        if q.project_id and not c.one("SELECT 1 AS ok FROM projects WHERE id = $1 AND org_id = $2",
                                      q.project_id, ctx.org_id):
            raise not_found("Projeto")
        return RD.evaluate(c, org_id=ctx.org_id, project_id=q.project_id)


@route("POST", "/v1/readiness/snapshots", query=N.ReadinessQ, min_role="member", status=201, tags=TW,
       summary="Grava o retrato da prontidão (append-only, para comparar ao longo do tempo)")
def readiness_snapshot(ctx: Ctx, q: N.ReadinessQ):
    with ctx.tx() as c:
        if q.project_id and not c.one("SELECT 1 AS ok FROM projects WHERE id = $1 AND org_id = $2",
                                      q.project_id, ctx.org_id):
            raise not_found("Projeto")
        return RD.snapshot(c, org_id=ctx.org_id, project_id=q.project_id)


@route("GET", "/v1/readiness/history", query=N.ReadinessQ, min_role="viewer", tags=TW)
def readiness_history(ctx: Ctx, q: N.ReadinessQ):
    with ctx.tx(readonly=True) as c:
        return {"items": RD.history(c, org_id=ctx.org_id, project_id=q.project_id),
                "dimensions": [{"key": k, "label": lb, "question": qu} for k, lb, qu in RD.DIMENSIONS],
                "weights": RD.WEIGHTS}


# ================================================================================================ recomendação
@route("GET", "/v1/recommendations", query=N.RecommendationQ, min_role="viewer", tags=TW,
       summary="Próximas ações, com razão e evidência (recomendação não é match)")
def recommendations(ctx: Ctx, q: N.RecommendationQ):
    with ctx.tx(readonly=True) as c:
        return {"items": RC.listing(c, org_id=ctx.org_id, status=q.status, limit=q.limit),
                "engine_version": RC.ENGINE_VERSION,
                "note": "Toda recomendação diz por quê e de onde veio. Match responde compatibilidade; "
                        "recomendação responde próxima ação."}


@route("POST", "/v1/recommendations/refresh", min_role="member", tags=TW,
       summary="Recalcula as recomendações (as que deixaram de valer ficam como superseded, não desaparecem)")
def refresh_recommendations(ctx: Ctx):
    with ctx.tx() as c:
        return RC.refresh(c, org_id=ctx.org_id, user_id=ctx.user_id)


@route("POST", "/v1/recommendations/{rec_id}/resolve", body=N.RecommendationResolveIn, min_role="member", tags=TW)
def resolve_recommendation(ctx: Ctx, body: N.RecommendationResolveIn):
    with ctx.tx() as c:
        return RC.resolve(c, rec_id=ctx.path["rec_id"], org_id=ctx.org_id, status=body.status, reason=body.reason)


# ================================================================================================ marketplace
@route("GET", "/v1/marketplace/feed", query=N.FeedQ, auth="none", tags=TM,
       summary="Feed público: lê SÓ anúncios publicados (a publicação é estado da entidade, não condição de consulta)")
def marketplace_feed(ctx: Ctx, q: N.FeedQ):
    with ctx.system_tx() as c:
        return MK.public_feed(c, subject_type=q.subject_type, seeking=q.seeking, territory=q.territory,
                              cause=q.cause, ods=q.ods, q=q.q, limit=q.limit, offset=q.offset)


@route("GET", "/v1/marketplace/listings/{listing_id}", auth="none", tags=TM)
def marketplace_item(ctx: Ctx):
    with ctx.system_tx() as c:
        return MK.view(c, ctx.path["listing_id"])


@route("GET", "/v1/marketplace/graph", auth="user", tags=TM, summary="Máquina de estados do anúncio")
def listing_graph(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": MK.graph(c), "states": [{"state": s, "label": MK.ST_LABEL[s]} for s in MK.STATES],
                "public_states": list(MK.PUBLIC_STATES), "seeking": list(MK.SEEKING),
                "subjects": list(MK.SUBJECTS)}


@route("POST", "/v1/marketplace/listings", body=N.ListingIn, min_role="manager", status=201, tags=TM,
       summary="Cria o anúncio em rascunho (nada nasce no ar)")
def create_listing(ctx: Ctx, body: N.ListingIn):
    with ctx.tx() as c:
        out = MK.create(c, org_id=ctx.org_id, actor=ctx.user_id, subject_type=body.subject_type,
                        subject_id=body.subject_id, headline=body.headline, summary=body.summary,
                        seeking=list(body.seeking), amount_target_cents=body.amount_target_cents,
                        currency=body.currency, territory=body.territory, causes=list(body.causes),
                        ods=list(body.ods), esg_tags=list(body.esg_tags), stage=body.stage,
                        expires_at=body.expires_at)
        ctx.audit(c, "listing.created", "listing", out["id"],
                  {"subject_type": body.subject_type, "subject_id": body.subject_id})
    return out


@route("GET", "/v1/marketplace/listings", query=N.ListingQ, min_role="viewer", tags=TM)
def my_listings(ctx: Ctx, q: N.ListingQ):
    with ctx.tx(readonly=True) as c:
        rows = MK.mine(c, org_id=ctx.org_id, state=q.state, limit=q.limit + 1, offset=q.offset)
    return page(rows, q.limit, q.offset)


@route("PATCH", "/v1/marketplace/listings/{listing_id}", body=N.ListingPatch, min_role="manager", tags=TM)
def patch_listing(ctx: Ctx, body: N.ListingPatch):
    lid = ctx.path["listing_id"]
    with ctx.tx() as c:
        fields = body.model_dump(exclude_unset=True, exclude_none=True)
        out = MK.update(c, listing_id=lid, org_id=ctx.org_id, fields=fields)
        ctx.audit(c, "listing.updated", "listing", lid, fields)
    return out


@route("POST", "/v1/marketplace/listings/{listing_id}/transition", body=N.ListingTransitionIn, min_role="manager",
       tags=TM, summary="Publica, pausa, arquiva (suspender e liberar são da administração)")
def transition_listing(ctx: Ctx, body: N.ListingTransitionIn):
    lid = ctx.path["listing_id"]
    with ctx.tx() as c:
        out = MK.transition(c, listing_id=lid, to=body.to, org_id=ctx.org_id, actor=ctx.user_id, note=body.note,
                            admin=ctx.admin_mode)
        if not out.get("unchanged"):
            ctx.audit(c, "listing.transition", "listing", lid, {"to": body.to, "note": body.note})
    return out


@route("POST", "/v1/admin/marketplace/listings/{listing_id}/transition", body=N.ListingTransitionIn, auth="admin",
       tags=TM, summary="Suspende ou libera anúncio (exige motivo registrado)")
def admin_transition_listing(ctx: Ctx, body: N.ListingTransitionIn):
    lid = ctx.path["listing_id"]
    with ctx.system_tx() as c:
        lst = c.one("SELECT org_id::text AS org_id FROM marketplace_listings WHERE id = $1", lid)
        if not lst:
            raise not_found("Anúncio")
        out = MK.transition(c, listing_id=lid, to=body.to, org_id=lst["org_id"], actor=ctx.user_id,
                            note=body.note, admin=True)
        ctx.audit(c, "admin.listing.transition", "listing", lid, {"to": body.to, "note": body.note},
                  org_id=lst["org_id"])
    return out


# ================================================================================================ relatório de impacto
@route("GET", "/v1/impact-updates/graph", auth="user", tags=TI)
def impact_graph(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": IR.graph(c), "statuses": [{"status": s, "label": IR.ST_LABEL[s]} for s in IR.STATUSES],
                "note": "Os números do relatório são apurados pelo servidor no envio, a partir das medições e "
                        "marcos do período. Quem revisa não é quem escreveu."}


@route("GET", "/v1/impact-updates/gather", query=N.GatherQ, min_role="viewer", tags=TI,
       summary="Prévia da apuração do período (mostra ANTES do envio o que será colhido)")
def impact_gather(ctx: Ctx, q: N.GatherQ):
    with ctx.tx(readonly=True) as c:
        if not c.one("SELECT 1 AS ok FROM projects WHERE id = $1 AND org_id = $2", q.project_id, ctx.org_id):
            raise not_found("Projeto")
        return IR.gather(c, project_id=q.project_id, period_start=q.period_start, period_end=q.period_end)


@route("POST", "/v1/impact-updates", body=N.ImpactUpdateIn, min_role="member", status=201, tags=TI)
def create_impact_update(ctx: Ctx, body: N.ImpactUpdateIn):
    if body.period_end < body.period_start:
        raise unprocessable("O fim do período não pode ser anterior ao início")
    with ctx.tx() as c:
        out = IR.create(c, project_id=body.project_id, org_id=ctx.org_id, actor=ctx.user_id,
                        period_start=body.period_start, period_end=body.period_end, summary=body.summary,
                        outputs=body.outputs, outcomes=body.outcomes, limitations=body.limitations,
                        risks_note=body.risks_note)
        ctx.audit(c, "impact_update.created", "impact_update", out["id"],
                  {"project_id": body.project_id,
                   "period": [str(body.period_start), str(body.period_end)]})
    return out


@route("GET", "/v1/impact-updates", query=N.ImpactUpdateQ, min_role="viewer", tags=TI)
def list_impact_updates(ctx: Ctx, q: N.ImpactUpdateQ):
    with ctx.tx(readonly=True) as c:
        rows = IR.listing(c, project_id=q.project_id, org_id=ctx.org_id, status=q.status, limit=q.limit + 1,
                          offset=q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/impact-updates/inbox", min_role="viewer", tags=TI,
       summary="Relatórios que esta organização pode analisar (dos projetos que ela apoia)")
def impact_inbox(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": IR.review_inbox(c, org_id=ctx.org_id, limit=30)}


@route("GET", "/v1/impact-updates/{update_id}", min_role="viewer", tags=TI)
def get_impact_update(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return IR.get(c, update_id=ctx.path["update_id"], org_id=ctx.org_id, admin=ctx.admin_mode)


@route("PATCH", "/v1/impact-updates/{update_id}", body=N.ImpactUpdatePatch, min_role="member", tags=TI)
def patch_impact_update(ctx: Ctx, body: N.ImpactUpdatePatch):
    uid = ctx.path["update_id"]
    with ctx.tx() as c:
        return IR.update(c, update_id=uid, org_id=ctx.org_id,
                         fields=body.model_dump(exclude_unset=True, exclude_none=True))


@route("POST", "/v1/impact-updates/{update_id}/transition", body=N.ImpactUpdateTransitionIn, min_role="manager",
       tags=TI, summary="Envia, analisa, pede ajuste, aceita ou publica — conforme o lado")
def transition_impact_update(ctx: Ctx, body: N.ImpactUpdateTransitionIn):
    uid = ctx.path["update_id"]
    with ctx.tx() as c:
        out = IR.transition(c, update_id=uid, to=body.to, org_id=ctx.org_id, actor=ctx.user_id, note=body.note,
                            admin=ctx.admin_mode)
        if not out.get("unchanged"):
            ctx.audit(c, "impact_update.transition", "impact_update", uid, {"to": body.to, "note": body.note})
    return out


@route("GET", "/v1/public/projects/{project_id}/impact", auth="none", tags=TI,
       summary="Relatórios PUBLICADOS de um projeto publicado")
def public_impact(ctx: Ctx):
    pid = ctx.path["project_id"]
    with ctx.system_tx() as c:
        p = c.one("SELECT visibility FROM projects WHERE id = $1", pid)
        if not p or p["visibility"] != "published":
            raise not_found("Projeto")
        return {"items": IR.published_for_project(c, pid)}


# ================================================================================================ perfil público
# A URL que a pessoa compartilha é `impacto.app/@identificador`, e ela precisa devolver PÁGINA, não JSON: quem
# recebe o link abre no navegador, e o WhatsApp/LinkedIn busca as metatags. Então `/@handle` é rota do SPA (servida
# pelo catch-all estático) e a API vive aqui, sob /v1. Registrar `/@{handle}` como rota de API sequestraria a URL
# pública — ela casa antes do catch-all — e o link compartilhado mostraria JSON cru.
@route("GET", "/v1/public/profiles/{handle}", auth="none", tags=TPF,
       summary="Perfil público: lê SÓ a projeção curada (public_fields), nunca tabela privada")
def public_profile(ctx: Ctx):
    with ctx.system_tx() as c:
        return PRO.public_page(c, ctx.path["handle"], authenticated=ctx.principal is not None)


@route("GET", "/v1/public/profiles/{handle}/open-graph", auth="none", tags=TPF,
       summary="Metadados de compartilhamento, montados da mesma projeção")
def profile_open_graph(ctx: Ctx):
    base = ctx.settings.public_base_url or ""
    with ctx.system_tx() as c:
        return PRO.open_graph(c, ctx.path["handle"], base_url=base)


@route("GET", "/v1/profiles/handle-available", query=N.HandleQ, auth="user", tags=TPF)
def handle_available(ctx: Ctx, q: N.HandleQ):
    with ctx.system_tx() as c:
        return PRO.available(c, q.handle)


@route("GET", "/v1/profiles/handle-suggest", query=N.SuggestQ, auth="user", tags=TPF)
def handle_suggest(ctx: Ctx, q: N.SuggestQ):
    with ctx.system_tx() as c:
        return {"items": PRO.suggest(c, q.base)}


@route("GET", "/v1/profiles/mine", min_role="viewer", tags=TPF)
def my_profiles(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"org": PRO.of_owner(c, org_id=ctx.org_id), "person": PRO.of_owner(c, user_id=ctx.user_id),
                "never_public": list(PRO.NEVER_PUBLIC),
                "projectable": [k for k, _, _ in PRO.PROJECTABLE]}


@route("POST", "/v1/profiles", body=N.ProfileIn, min_role="manager", status=201, tags=TPF,
       summary="Cria o perfil público (@identificador único, com normalização e reservas)")
def create_profile(ctx: Ctx, body: N.ProfileIn):
    # Identificador é global: a verificação de unicidade e a reserva precisam enxergar além do inquilino (ADR 105).
    with ctx.system_tx() as c:
        if body.owner == "org":
            ctx.require_role("manager")
            out = PRO.create(c, handle=body.handle, display_name=body.display_name, org_id=ctx.org_id,
                             headline=body.headline, bio=body.bio, actor=ctx.user_id)
        else:
            out = PRO.create(c, handle=body.handle, display_name=body.display_name, user_id=ctx.user_id,
                             headline=body.headline, bio=body.bio, actor=ctx.user_id)
        ctx.audit(c, "profile.created", "public_profile", out["id"],
                  {"handle": out["handle"], "owner": body.owner})
    return out


@route("PATCH", "/v1/profiles/{profile_id}", body=N.ProfilePatch, min_role="viewer", tags=TPF,
       summary="Edita o perfil e remonta a projeção pública")
def patch_profile(ctx: Ctx, body: N.ProfilePatch):
    pid = ctx.path["profile_id"]
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    if "links" in fields:
        fields["links"] = [dict(x) for x in fields["links"]]
    with ctx.system_tx() as c:
        owner = c.one("SELECT org_id::text AS org_id, user_id::text AS user_id FROM public_profiles WHERE id = $1",
                      pid)
        if not owner:
            raise not_found("Perfil")
        if owner["org_id"]:
            if owner["org_id"] != ctx.org_id:
                raise forbidden("Perfil de outra organização")
            ctx.require_role("manager")
        elif owner["user_id"] != ctx.user_id:
            raise forbidden("Perfil de outra pessoa")
        out = PRO.update(c, profile_id=pid, org_id=ctx.org_id, user_id=ctx.user_id, fields=fields,
                         actor=ctx.user_id)
        ctx.audit(c, "profile.updated", "public_profile", pid, {"fields": sorted(fields.keys())})
    return out


@route("POST", "/v1/profiles/{profile_id}/rebuild", min_role="viewer", tags=TPF,
       summary="Remonta a projeção pública a partir do estado atual")
def rebuild_profile(ctx: Ctx):
    pid = ctx.path["profile_id"]
    with ctx.system_tx() as c:
        owner = c.one("SELECT org_id::text AS org_id, user_id::text AS user_id FROM public_profiles WHERE id = $1",
                      pid)
        if not owner:
            raise not_found("Perfil")
        if owner["org_id"] and owner["org_id"] != ctx.org_id:
            raise forbidden("Perfil de outra organização")
        if owner["user_id"] and owner["user_id"] != ctx.user_id:
            raise forbidden("Perfil de outra pessoa")
        return PRO.rebuild_projection(c, profile_id=pid)


@route("GET", "/v1/profiles/{profile_id}/handle-history", min_role="viewer", tags=TPF,
       summary="Histórico de identificadores (append-only: trocar é permitido, apagar o rastro não)")
def profile_handle_history(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": PRO.handle_timeline(c, ctx.path["profile_id"])}


# ================================================================================================ taxonomia
@route("GET", "/v1/taxonomies", query=N.TaxonomyQ, auth="user", tags=TX,
       summary="Taxonomias versionadas com política de uso de cada uma")
def taxonomies(ctx: Ctx, q: N.TaxonomyQ):
    with ctx.tx(readonly=True) as c:
        taxes = c.query(
            # `taxonomies` não tem label_en (só os TERMOS têm): a tabela guarda o rótulo em português e a
            # política de uso. Eu havia selecionado a coluna por simetria com taxonomy_terms, e a rota caía em 500.
            "SELECT key, label_pt, purpose, sensitivity, usage_policy, source_name, source_url, source_date,"
            " active, version, updated_at FROM taxonomies WHERE ($1::text IS NULL OR key = $1)"
            " ORDER BY key", q.taxonomy)
        for t in taxes:
            t["terms"] = c.query(
                "SELECT code, label_pt, label_en, description, position, active FROM taxonomy_terms"
                " WHERE taxonomy = $1 AND ($2 OR active) ORDER BY position, code", t["key"], q.include_inactive)
    return {"items": taxes,
            "note": "Rótulo não se escreve na interface: vem daqui, com versão. Termos de sensibilidade "
                    "'beneficiary_group' descrevem PROJETO ou NECESSIDADE e não podem ser usados para filtrar, "
                    "segmentar ou inferir característica de pessoa."}


# ================================================================================================ território
@route("POST", "/v1/territory/needs", body=N.TerritoryNeedIn, min_role="member", status=201, tags=TT,
       summary="Registra necessidade do território (estimativa exige fonte declarada)")
def create_territory_need(ctx: Ctx, body: N.TerritoryNeedIn):
    if body.people_estimate is not None and not body.source_name:
        raise unprocessable("Estimativa de pessoas exige a fonte do número (source_name)")
    with ctx.tx() as c:
        row = c.one(
            "INSERT INTO territory_needs(territory, org_id, title, description, cause, ods, beneficiary_groups,"
            " people_estimate, source_name, source_url, source_date, priority, created_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING id::text AS id, status, created_at",
            body.territory, ctx.org_id, body.title, body.description, body.cause, list(body.ods),
            list(body.beneficiary_groups), body.people_estimate, body.source_name, body.source_url,
            body.source_date, body.priority, ctx.user_id)
        ctx.audit(c, "territory_need.created", "territory_need", row["id"],
                  {"territory": body.territory, "priority": body.priority})
    return row


@route("GET", "/v1/territory/needs", query=N.TerritoryNeedQ, auth="user", tags=TT)
def list_territory_needs(ctx: Ctx, q: N.TerritoryNeedQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query(
            "SELECT n.id::text AS id, n.territory, n.title, n.description, n.cause, n.ods, n.beneficiary_groups,"
            " n.people_estimate, n.source_name, n.source_url, n.source_date, n.priority, n.status, n.visibility,"
            " n.created_at, coalesce(o.trade_name, o.legal_name) AS org_name FROM territory_needs n"
            " LEFT JOIN organizations o ON o.id = n.org_id"
            " WHERE ($1::text IS NULL OR n.territory = $1 OR n.territory LIKE $1 || '-%')"
            "   AND ($2::text IS NULL OR n.cause = $2) AND ($3::text IS NULL OR n.status = $3)"
            # ordena pelo PESO da prioridade, não pelo texto: 'critical' > 'high' > 'medium' > 'low'
            " ORDER BY (CASE n.priority WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END) DESC, n.created_at DESC LIMIT $4 OFFSET $5",
            q.territory, q.cause, q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


# ================================================================================================ experiência profissional
@route("POST", "/v1/profile/experiences", body=N.ExperienceIn, auth="user", status=201, tags=TPF,
       summary="Declara experiência profissional (nasce 'declarada'; confirmação é de quem administra a organização)")
def create_experience(ctx: Ctx, body: N.ExperienceIn):
    with ctx.tx() as c:
        row = c.one(
            "INSERT INTO professional_experiences(user_id, org_id, org_name, project_id, role, description,"
            " started_on, ended_on, evidence_document_id, visibility,"
            " state) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,"
            " CASE WHEN $2::uuid IS NULL THEN 'declared' ELSE 'pending_confirmation' END)"
            " RETURNING id::text AS id, state, created_at",
            ctx.user_id, body.org_id, body.org_name, body.project_id, body.role, body.description,
            body.started_on, body.ended_on, body.evidence_document_id, body.visibility)
        ctx.audit(c, "experience.declared", "professional_experience", row["id"],
                  {"org_id": body.org_id, "role": body.role})
    return {**row,
            "note": "Experiência declarada não entra no perfil público. Só a confirmada por quem administra a "
                    "organização citada aparece."}


@route("GET", "/v1/profile/experiences", auth="user", tags=TPF)
def list_experiences(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query(
            "SELECT e.id::text AS id, e.role, e.org_name, e.org_id::text AS org_id, e.project_id::text AS"
            " project_id, e.description, e.started_on, e.ended_on, e.state, e.visibility, e.dispute_note,"
            " e.confirmed_at, user_display_name(e.confirmed_by) AS confirmed_by_name"
            " FROM professional_experiences e WHERE e.user_id = $1 ORDER BY e.started_on DESC NULLS LAST",
            ctx.user_id)}


@route("GET", "/v1/org/experience-requests", min_role="manager", tags=TPF,
       summary="Experiências que pessoas declararam na sua organização e aguardam confirmação")
def experience_requests(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query(
            "SELECT e.id::text AS id, e.user_id::text AS user_id, user_display_name(e.user_id) AS person,"
            " e.role, e.description, e.started_on, e.ended_on, e.state, e.created_at,"
            " e.evidence_document_id::text AS evidence_document_id FROM professional_experiences e"
            " WHERE e.org_id = $1 AND e.state IN ('declared','pending_confirmation')"
            " ORDER BY e.created_at", ctx.org_id)}


@route("POST", "/v1/org/experience-requests/{experience_id}/decide", body=N.ExperienceDecisionIn,
       min_role="manager", tags=TPF,
       summary="Confirma ou contesta a experiência (quem confirma não pode ser a própria pessoa)")
def decide_experience(ctx: Ctx, body: N.ExperienceDecisionIn):
    eid = ctx.path["experience_id"]
    with ctx.tx() as c:
        e = c.one("SELECT user_id::text AS user_id, org_id::text AS org_id, state FROM professional_experiences"
                  " WHERE id = $1", eid)
        if not e or e["org_id"] != ctx.org_id:
            raise not_found("Experiência")
        if e["user_id"] == ctx.user_id:
            raise forbidden("Ninguém confirma a própria experiência", "self_confirm")
        if e["state"] in ("confirmed", "revoked"):
            raise ApiError(409, "already_decided", f"Experiência já está como {e['state']}")
        if body.decision == "disputed" and not (body.note and len(body.note.strip()) >= 3):
            raise unprocessable("Contestar exige dizer o motivo")
        c.run("UPDATE professional_experiences SET state = $2, confirmed_by = $3, confirmed_at = now(),"
              " dispute_note = $4 WHERE id = $1", eid, body.decision, ctx.user_id, body.note)
        ctx.audit(c, f"experience.{body.decision}", "professional_experience", eid, {"note": body.note})
        from ..network import notify as NT
        NT.org_event(c, event="Experience.confirmed" if body.decision == "confirmed" else "Experience.disputed",
                     org_id=ctx.org_id, actor_user_id=ctx.user_id,
                     title="Experiência confirmada" if body.decision == "confirmed" else "Experiência contestada",
                     body=body.note or "Decisão registrada.", link="/rede/experiencias",
                     ref_type="experience", ref_id=eid, min_role="manager")
    return {"id": eid, "state": body.decision}


# ================================================================================================ moderação
@route("GET", "/v1/moderation/ladder", auth="user", tags=("moderacao",),
       summary="A escada de medidas, com o que cada degrau significa e se exige prazo")
def moderation_ladder(ctx: Ctx):
    return {"items": ENF.ladder(), "categories": [{"code": c, "label": lb} for c, lb in ENF.CATEGORIES],
            "max_jump": ENF.MAX_JUMP,
            "note": "Medida exige regra e motivo. Nenhuma medida é aplicada automaticamente: heurística prioriza a "
                    "fila, nunca decide. Quem julga a contestação não é quem aplicou."}


@route("GET", "/v1/conta/moderacao", min_role="admin", tags=("moderacao",),
       summary="Medidas de moderação contra a sua organização, com o direito de contestar")
def my_enforcement(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": ENF.target_view(c, org_id=ctx.org_id, user_id=ctx.user_id),
                "note": "A identidade de quem denuncia nunca é revelada ao alvo da denúncia."}


@route("POST", "/v1/conta/moderacao/{action_id}/contestar", body=N.AppealIn, min_role="admin",
       tags=("moderacao",), summary="Contesta uma medida (uma vez por medida)")
def appeal_enforcement(ctx: Ctx, body: N.AppealIn):
    with ctx.tx() as c:
        out = ENF.appeal(c, action_id=ctx.path["action_id"], org_id=ctx.org_id, user_id=ctx.user_id,
                         note=body.note)
        ctx.audit(c, "enforcement.appealed", "enforcement", ctx.path["action_id"], {})
    return out


@route("GET", "/v1/admin/enforcement", query=N.EnforcementQ, auth="admin", tags=("moderacao",))
def list_enforcement(ctx: Ctx, q: N.EnforcementQ):
    with ctx.system_tx() as c:
        rows = c.query(
            "SELECT e.id::text AS id, e.measure, e.severity, e.rule_ref, e.reason, e.status, e.starts_at,"
            " e.ends_at, e.appeal_at, e.appeal_note, e.appeal_decision, e.created_at,"
            " e.target_org_id::text AS target_org_id, e.target_user_id::text AS target_user_id,"
            " coalesce(o.trade_name, o.legal_name) AS target_org_name,"
            " user_display_name(e.target_user_id) AS target_user_name,"
            " user_display_name(e.decided_by) AS decided_by_name,"
            " user_display_name(e.appeal_decided_by) AS appeal_decided_by_name"
            " FROM enforcement_actions e LEFT JOIN organizations o ON o.id = e.target_org_id"
            " WHERE ($1::text IS NULL OR e.status = $1) ORDER BY e.created_at DESC LIMIT $2 OFFSET $3",
            q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/admin/enforcement", body=N.EnforcementIn, auth="admin", status=201, tags=("moderacao",),
       summary="Aplica medida (proporcional ao histórico; contornar a escada exige justificativa registrada)")
def apply_enforcement(ctx: Ctx, body: N.EnforcementIn):
    with ctx.system_tx() as c:
        out = ENF.apply(c, measure=body.measure, decided_by=ctx.user_id, rule_ref=body.rule_ref,
                        reason=body.reason, target_org_id=body.target_org_id, target_user_id=body.target_user_id,
                        report_id=body.report_id, evidence_note=body.evidence_note, ends_at=body.ends_at,
                        override_reason=body.override_reason)
        ctx.audit(c, "admin.enforcement_applied", "enforcement", out["id"],
                  {"measure": body.measure, "rule_ref": body.rule_ref,
                   "escalation_override": out["escalation_override"]},
                  org_id=body.target_org_id)
    return out


@route("GET", "/v1/admin/enforcement/history", query=N.EnforcementHistoryQ, auth="admin", tags=("moderacao",),
       summary="Histórico de medidas contra um alvo — é o que torna a proporcionalidade verificável")
def enforcement_history(ctx: Ctx, q: N.EnforcementHistoryQ):
    if not q.org_id and not q.user_id:
        raise unprocessable("Informe o alvo: org_id ou user_id")
    with ctx.system_tx() as c:
        prior = ENF.history(c, org_id=q.org_id, user_id=q.user_id)
    return {"items": prior,
            "next_allowed": [m for m in ENF.MEASURES if ENF.escalation_ok(m, prior)[0]],
            "note": "A próxima medida permitida depende do histórico. Subir mais do que isso exige justificativa "
                    "registrada, que fica marcada na medida."}


@route("POST", "/v1/admin/enforcement/{action_id}/lift", body=N.AppealIn, auth="admin", tags=("moderacao",),
       summary="Levanta a medida (exige motivo, como aplicar)")
def lift_enforcement(ctx: Ctx, body: N.AppealIn):
    with ctx.system_tx() as c:
        out = ENF.lift(c, action_id=ctx.path["action_id"], decided_by=ctx.user_id, note=body.note)
        ctx.audit(c, "admin.enforcement_lifted", "enforcement", ctx.path["action_id"], {"note": body.note})
    return out


@route("POST", "/v1/admin/enforcement/{action_id}/appeal-decision", body=N.AppealDecisionIn, auth="admin",
       tags=("moderacao",), summary="Julga a contestação (nunca quem aplicou a medida)")
def decide_appeal(ctx: Ctx, body: N.AppealDecisionIn):
    with ctx.system_tx() as c:
        out = ENF.decide_appeal(c, action_id=ctx.path["action_id"], decided_by=ctx.user_id,
                                uphold=body.uphold, note=body.note)
        ctx.audit(c, "admin.enforcement_appeal", "enforcement", ctx.path["action_id"],
                  {"uphold": body.uphold})
    return out


# ================================================================================================ eventos de domínio
@route("GET", "/v1/network/events", query=N.EventQ, min_role="viewer", tags=TW,
       summary="Fatos recentes da organização (a fonte única que alimenta avisos, linha de tempo e auditoria)")
def domain_events(ctx: Ctx, q: N.EventQ):
    with ctx.tx(readonly=True) as c:
        rows = EV.feed(c, org_id=ctx.org_id, project_id=q.project_id, limit=q.limit + 1, offset=q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/projects/{project_id}/team", min_role="viewer", tags=TW,
       summary="Quem é a equipe do projeto — e portanto quem será avisado em cada mudança")
def project_team(ctx: Ctx):
    pid = ctx.path["project_id"]
    from ..network import notify as NT
    with ctx.tx(readonly=True) as c:
        if not c.one("SELECT 1 AS ok FROM projects WHERE id = $1", pid):
            raise not_found("Projeto")
        rows = NT.team(c, pid)
    return {"items": rows, "count": len(rows),
            "note": "A equipe cresce sozinha quando nasce uma relação de participação ou uma candidatura é aceita. "
                    "Quem age não recebe aviso do próprio ato."}
