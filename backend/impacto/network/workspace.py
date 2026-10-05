"""Workspace: o ambiente de trabalho de cada persona. **Não** é "dashboard por perfil".

CORREÇÃO CONCEITUAL PEDIDA (anexo de correções, item 1, verbatim): "Não chame isso de 'dashboard por perfil'; chame de
Workspace. Essa diferença parece pequena, mas arquiteturalmente é enorme." E a razão dita no próprio pedido:

    o investidor quer um ambiente de DECISÃO e RELACIONAMENTO;
    a organização quer um ambiente de CONSTRUÇÃO, CAPTAÇÃO e EXECUÇÃO;
    o profissional quer um ambiente de OPORTUNIDADES e ATUAÇÃO;
    o governo quer um ambiente de POLÍTICA PÚBLICA, TERRITÓRIO e ACOMPANHAMENTO.

A diferença arquitetural é concreta e está neste arquivo: um dashboard devolve NÚMEROS; um workspace devolve
**próximas ações** com destino e razão. `WorkspaceContext` é isso — quem sou, o que posso, o que me espera agora e
onde clico. A interface desenha; não decide.

UM NÚCLEO, VÁRIAS EXPERIÊNCIAS: as quatro personas chamam os MESMOS motores (proposta, relação, recomendação,
prontidão, marketplace). O que muda é a seleção e a ordem — não há quatro produtos, não há domínio duplicado. É
exatamente o que o pedido manda provar: "provar que Investidor, Organização, Profissional e Governo conseguem
participar do mesmo ciclo de impacto sem duplicar domínio, quebrar permissões ou criar quatro produtos independentes".

PERSONA NÃO DÁ PERMISSÃO. Persona orienta o que aparece primeiro; quem pode fazer o quê continua sendo papel na
organização + entitlement do plano + RLS. Confundir os dois seria transformar uma preferência de visualização em
escalonamento de privilégio.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection
from ..http import unprocessable
from . import marketplace, messaging, proposals, readiness, recommendation, relationships

#: Persona padrão por tipo de organização, quando nenhuma foi declarada. Chute explícito e sobrescrevível, não mágica.
DEFAULT_PERSONA = {"osc": "organization", "company": "investor", "provider": "professional",
                   "government": "government", "individual": "donor", "platform": "admin"}

#: Seções de cada workspace, EM ORDEM. A ordem é a decisão de produto: o que a persona olha primeiro.
LAYOUT: dict[str, tuple[tuple[str, str], ...]] = {
    "organization": (
        ("next_actions", "O que fazer agora"),
        ("readiness", "Prontidão dos seus projetos"),
        ("proposals_in", "Propostas recebidas"),
        ("projects", "Seus projetos"),
        ("listings", "Seus anúncios"),
        ("reports_due", "Prestação de contas"),
        ("conversations", "Conversas"),
        ("network", "Sua rede"),
    ),
    "investor": (
        ("next_actions", "O que fazer agora"),
        ("pipeline", "Projetos em avaliação"),
        ("proposals_out", "Propostas enviadas"),
        ("supported", "Projetos que você apoia"),
        ("reports_to_review", "Relatórios para analisar"),
        ("discover", "Descobrir projetos"),
        ("conversations", "Conversas"),
        ("network", "Sua rede"),
    ),
    "professional": (
        ("next_actions", "O que fazer agora"),
        ("opportunities", "Oportunidades de atuação"),
        ("proposals_out", "Propostas enviadas"),
        ("engagements", "Atuações em andamento"),
        ("profile", "Seu perfil público"),
        ("credentials", "Registros e experiências"),
        ("conversations", "Conversas"),
    ),
    "government": (
        ("next_actions", "O que fazer agora"),
        ("territory", "Território e necessidades"),
        ("programs", "Programas e editais"),
        ("monitored", "Projetos acompanhados"),
        ("reports_to_review", "Relatórios para analisar"),
        ("indicators", "Indicadores do território"),
        ("conversations", "Conversas"),
    ),
    "donor": (("next_actions", "O que fazer agora"), ("supported", "Projetos que você apoia"),
              ("discover", "Descobrir projetos"), ("reports_to_review", "Prestação de contas recebida"),
              ("conversations", "Conversas")),
    "mentor": (("next_actions", "O que fazer agora"), ("opportunities", "Pedidos de mentoria"),
               ("engagements", "Mentorias em andamento"), ("profile", "Seu perfil público"),
               ("conversations", "Conversas")),
    "volunteer": (("next_actions", "O que fazer agora"), ("opportunities", "Vagas de voluntariado"),
                  ("engagements", "Participações"), ("profile", "Seu perfil público")),
    "researcher": (("next_actions", "O que fazer agora"), ("discover", "Projetos e evidências"),
                   ("indicators", "Indicadores publicados"), ("profile", "Seu perfil público")),
    "educator": (("next_actions", "O que fazer agora"), ("opportunities", "Oportunidades de formação"),
                 ("engagements", "Formações em andamento"), ("profile", "Seu perfil público")),
    "admin": (("next_actions", "Fila de administração"), ("moderation", "Denúncias e medidas"),
              ("queues", "Filas de análise"), ("platform", "Saúde da plataforma")),
}


def personas(conn: Connection, *, org_kind: str | None = None) -> list[dict]:
    return conn.query(
        "SELECT key, label_pt, label_en, org_kinds, primary_job, position FROM personas"
        " WHERE active AND ($1::text IS NULL OR $1 = ANY(org_kinds)) ORDER BY position", org_kind)


def declare(conn: Connection, *, org_id: str, persona: str, actor: str | None, primary: bool = False) -> dict:
    """Declara uma persona para a organização. Mais de uma é normal: uma empresa investe E presta serviço."""
    p = conn.one("SELECT key, org_kinds, label_pt FROM personas WHERE key = $1 AND active", persona)
    if not p:
        raise unprocessable(f"Persona desconhecida: {persona}")
    kind = conn.scalar("SELECT kind FROM organizations WHERE id = $1", org_id)
    if p["org_kinds"] and kind not in p["org_kinds"]:
        raise unprocessable(
            f"A persona “{p['label_pt']}” não se aplica a organizações do tipo {kind}",
            {"aplica_a": list(p["org_kinds"])})
    if primary:
        conn.run("UPDATE org_personas SET is_primary = false WHERE org_id = $1 AND is_primary", org_id)
    conn.run("INSERT INTO org_personas(org_id, persona, is_primary, declared_by) VALUES ($1,$2,$3,$4)"
             " ON CONFLICT (org_id, persona) DO UPDATE SET is_primary = excluded.is_primary", org_id, persona,
             primary, actor)
    return {"org_id": org_id, "persona": persona, "is_primary": primary, "label": p["label_pt"]}


def undeclare(conn: Connection, *, org_id: str, persona: str) -> dict:
    n = conn.run("DELETE FROM org_personas WHERE org_id = $1 AND persona = $2", org_id, persona)
    return {"removed": n}


def active_persona(conn: Connection, *, org_id: str, org_kind: str, asked: str | None = None) -> dict:
    """Qual persona orienta este workspace agora.

    Ordem: a pedida (se declarada) → a principal declarada → a primeira declarada → o padrão do tipo de organização.
    O resultado diz de onde veio, para que a interface possa oferecer "você também atua como…".
    """
    declared = conn.query("SELECT persona, is_primary FROM org_personas WHERE org_id = $1", org_id)
    keys = [d["persona"] for d in declared]
    if asked and asked in keys:
        return {"persona": asked, "source": "asked", "declared": keys}
    primary = next((d["persona"] for d in declared if d["is_primary"]), None)
    if primary:
        return {"persona": primary, "source": "primary", "declared": keys}
    if keys:
        return {"persona": keys[0], "source": "declared", "declared": keys}
    fallback = DEFAULT_PERSONA.get(org_kind, "organization")
    return {"persona": fallback, "source": "default_by_org_kind", "declared": []}


# ------------------------------------------------------------------------------------------------ o contexto

def context(conn: Connection, *, org_id: str, org_kind: str, user_id: str | None, role: str,
            persona: str | None = None, platform_admin: bool = False) -> dict[str, Any]:
    """O WorkspaceContext: quem sou, o que posso, o que me espera e onde clico.

    Uma chamada só. Sem isso, a abertura do produto viram oito requisições e a persona fica decidida no navegador —
    que é onde ela não pode ser decidida, porque navegador não é autoridade.
    """
    act = active_persona(conn, org_id=org_id, org_kind=org_kind, asked=persona)
    key = "admin" if platform_admin and (persona == "admin") else act["persona"]
    layout = LAYOUT.get(key, LAYOUT["organization"])
    meta = conn.one("SELECT label_pt, primary_job FROM personas WHERE key = $1", key) or {}

    counts = {
        "proposals": proposals.counts(conn, org_id),
        "relationships": relationships.counts(conn, org_id),
        "recommendations": recommendation.counts(conn, org_id),
        "unread_messages": messaging.unread_count(conn, org_id),
        "notifications": int(conn.scalar(
            "SELECT count(*) FROM notifications WHERE user_id = $1 AND read_at IS NULL", user_id) or 0)
        if user_id else 0,
    }
    recs = recommendation.listing(conn, org_id=org_id, limit=6)
    if not recs:
        # Primeira abertura: a caixa de recomendações está vazia porque ninguém calculou ainda, não porque não há
        # o que fazer. Calcular aqui é barato e evita um workspace vazio sem explicação.
        recommendation.refresh(conn, org_id=org_id, user_id=user_id, limit=20)
        recs = recommendation.listing(conn, org_id=org_id, limit=6)

    return {
        "persona": {"key": key, "label": meta.get("label_pt"), "job": meta.get("primary_job"),
                    "source": act["source"], "declared": act["declared"],
                    "available": [p["key"] for p in personas(conn, org_kind=org_kind)]},
        "actor": {"org_id": org_id, "org_kind": org_kind, "user_id": user_id, "role": role,
                  "platform_admin": platform_admin},
        "capabilities": capabilities(conn, org_id=org_id, org_kind=org_kind, role=role,
                                     platform_admin=platform_admin),
        "layout": [{"key": k, "title": t} for k, t in layout],
        "counts": counts,
        "next_actions": recs,
        "sections": {k: _section(conn, k, org_id=org_id, user_id=user_id, org_kind=org_kind) for k, _ in layout},
        "note": "Persona orienta a ordem do que aparece. Permissão continua vindo de papel, plano e RLS.",
    }


#: O que cada capacidade exige. `role` usa a escala de papéis da plataforma; `kinds` restringe por tipo de organização.
#: Esta tabela NÃO substitui a autorização da rota — ela diz à interface o que oferecer, e as duas precisam concordar.
CAPABILITIES: dict[str, dict[str, Any]] = {
    "create_project": {"roles": ("member", "analyst", "manager", "admin", "owner"), "kinds": ("osc", "government")},
    "publish_project": {"roles": ("manager", "admin", "owner"), "kinds": ("osc", "government")},
    "create_listing": {"roles": ("manager", "admin", "owner"), "kinds": None},
    "send_proposal": {"roles": ("manager", "admin", "owner"), "kinds": None},
    "decide_proposal": {"roles": ("manager", "admin", "owner"), "kinds": None},
    "submit_impact_report": {"roles": ("manager", "admin", "owner"), "kinds": ("osc", "government")},
    "review_impact_report": {"roles": ("manager", "admin", "owner"),
                             "kinds": ("company", "government", "individual")},
    "manage_team": {"roles": ("admin", "owner"), "kinds": None},
    "manage_billing": {"roles": ("owner",), "kinds": None},
    "edit_public_profile": {"roles": ("manager", "admin", "owner"), "kinds": None},
    "run_match": {"roles": ("analyst", "manager", "admin", "owner"), "kinds": None},
    "publish_call": {"roles": ("manager", "admin", "owner"), "kinds": ("government", "company")},
    "register_territory_need": {"roles": ("member", "analyst", "manager", "admin", "owner"),
                                "kinds": ("government", "osc")},
    "moderate": {"roles": (), "kinds": None, "platform_admin": True},
}


def capabilities(conn: Connection, *, org_id: str, org_kind: str, role: str,
                 platform_admin: bool = False) -> dict[str, bool]:
    """O que esta pessoa, nesta organização, pode fazer — para a interface não oferecer o que a rota vai recusar."""
    out: dict[str, bool] = {}
    for key, rule in CAPABILITIES.items():
        if rule.get("platform_admin"):
            out[key] = bool(platform_admin)
            continue
        ok = role in rule["roles"] or platform_admin
        if ok and rule["kinds"]:
            ok = org_kind in rule["kinds"] or platform_admin
        out[key] = bool(ok)
    return out


# ------------------------------------------------------------------------------------------------ seções

def _section(conn: Connection, key: str, *, org_id: str, user_id: str | None, org_kind: str) -> Any:
    fn = _SECTIONS.get(key)
    return fn(conn, org_id=org_id, user_id=user_id, org_kind=org_kind) if fn else None


def _s_next_actions(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return recommendation.listing(conn, org_id=org_id, limit=10)


def _s_readiness(conn: Connection, *, org_id: str, **_: Any) -> Any:
    """Prontidão dos projetos abertos. Calcula no máximo cinco: a abertura não pode ficar lenta por completude."""
    projs = conn.query(
        "SELECT id::text AS id, title FROM projects WHERE org_id = $1"
        " AND status NOT IN ('archived','cancelled','rejected','completed') ORDER BY updated_at DESC LIMIT 5",
        org_id)
    out = []
    for p in projs:
        r = readiness.evaluate(conn, org_id=org_id, project_id=p["id"])
        out.append({"project_id": p["id"], "title": p["title"], "overall": r["overall"], "band": r["band"],
                    "scores": r["scores"], "blockers": r["blockers"][:3]})
    return out


def _s_proposals_in(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return proposals.inbox(conn, org_id=org_id, box="received", status="open", limit=10)


def _s_proposals_out(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return proposals.inbox(conn, org_id=org_id, box="sent", limit=10)


def _s_projects(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return conn.query(
        "SELECT p.id::text AS id, p.title, p.status, p.visibility, p.budget_total_cents, p.updated_at,"
        " (SELECT committed_cents FROM project_funding(p.id)) AS committed_cents,"
        " (SELECT count(*) FROM project_team(p.id)) AS team_size"
        " FROM projects p WHERE p.org_id = $1 AND p.status NOT IN ('archived','cancelled')"
        " ORDER BY p.updated_at DESC LIMIT 10", org_id)


def _s_listings(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return marketplace.mine(conn, org_id=org_id, limit=10)


def _s_reports_due(conn: Connection, *, org_id: str, **_: Any) -> Any:
    """Projetos em execução e o último relatório aceito de cada um. É a tela de "quem está devendo prestação"."""
    return conn.query(
        "SELECT p.id::text AS id, p.title, p.status,"
        " (SELECT max(u.period_end) FROM impact_updates u WHERE u.project_id = p.id"
        "    AND u.status IN ('accepted','published')) AS last_accepted_period,"
        " (SELECT u.status FROM impact_updates u WHERE u.project_id = p.id"
        "  ORDER BY u.period_end DESC LIMIT 1) AS latest_status"
        " FROM projects p WHERE p.org_id = $1 AND p.status IN ('funded','in_execution','monitoring')"
        " ORDER BY p.updated_at DESC LIMIT 10", org_id)


def _s_conversations(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return messaging.threads(conn, org_id=org_id, limit=8)


def _s_network(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return {"relationships": relationships.mine(conn, org_id=org_id, status="active", limit=10),
            "pending": relationships.mine(conn, org_id=org_id, status="pending", direction="in", limit=10),
            "graph": relationships.graph(conn, org_id=org_id, depth=1, limit=30)}


def _s_pipeline(conn: Connection, *, org_id: str, **_: Any) -> Any:
    """Para quem investe: o que está em avaliação. Favorito e acompanhamento são PRIVADOS — por isso só a própria
    organização vê esta seção, e a RLS garante isso independentemente desta consulta."""
    return conn.query(
        "SELECT r.id::text AS id, r.kind, r.created_at, r.target_project_id::text AS project_id, p.title,"
        " p.status, p.budget_total_cents, coalesce(o.trade_name, o.legal_name) AS org_name"
        " FROM relationships r JOIN projects p ON p.id = r.target_project_id"
        " JOIN organizations o ON o.id = p.org_id"
        " WHERE r.source_org_id = $1 AND r.kind IN ('favorite','watchlist','contact') AND r.status = 'active'"
        " ORDER BY r.created_at DESC LIMIT 15", org_id)


def _s_supported(conn: Connection, *, org_id: str, **_: Any) -> Any:
    """Projetos apoiados, com a distinção que a plataforma não deixa borrar: intenção ≠ compromisso ≠ recebido."""
    return conn.query(
        "SELECT p.id::text AS id, p.title, p.status, coalesce(o.trade_name, o.legal_name) AS org_name,"
        " i.status AS intent_status, i.amount_cents AS intent_amount_cents, i.currency,"
        " (i.commitment_id IS NOT NULL) AS has_commitment,"
        " (SELECT committed_cents FROM project_funding(p.id)) AS project_committed_cents"
        " FROM investment_intents i JOIN projects p ON p.id = i.project_id"
        " JOIN organizations o ON o.id = p.org_id"
        " WHERE i.investor_org_id = $1 ORDER BY i.updated_at DESC LIMIT 15", org_id)


def _s_reports_to_review(conn: Connection, *, org_id: str, **_: Any) -> Any:
    """Relatórios que ESTA organização pode analisar: dos projetos que ela apoia, enviados e ainda sem decisão."""
    return conn.query(
        "SELECT u.id::text AS id, u.project_id::text AS project_id, p.title AS project_title, u.period_start,"
        " u.period_end, u.status, u.submitted_at, u.evidence_count,"
        " coalesce(o.trade_name, o.legal_name) AS org_name"
        " FROM impact_updates u JOIN projects p ON p.id = u.project_id"
        " JOIN organizations o ON o.id = u.org_id"
        " WHERE u.status IN ('submitted','under_review') AND u.org_id <> $1"
        "   AND (EXISTS (SELECT 1 FROM applications a WHERE a.project_id = u.project_id"
        "                  AND a.funder_org_id = $1 AND a.status IN ('approved','accepted','contracted'))"
        "     OR EXISTS (SELECT 1 FROM relationships r WHERE r.target_project_id = u.project_id"
        "                  AND r.source_org_id = $1 AND r.status = 'active'"
        "                  AND r.kind IN ('investment','sponsorship','support','government_support',"
        "                                 'project_sponsor','project_investor')))"
        " ORDER BY u.submitted_at NULLS LAST LIMIT 10", org_id)


def _s_discover(conn: Connection, *, org_id: str, **_: Any) -> Any:
    """Descobrir projetos: lê o FEED PÚBLICO do marketplace, não a tabela de projetos.

    Esta escolha é o ponto do achado E6: a seção de descoberta de qualquer persona passa por
    `marketplace.public_feed()`, que tem o filtro de publicação escrito uma vez. Não há como esta seção vazar
    rascunho, porque ela não sabe consultar projeto.
    """
    return marketplace.public_feed(conn, limit=12)["items"]


def _s_opportunities(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return marketplace.public_feed(
        conn, seeking="professional", limit=12)["items"] + marketplace.public_feed(
        conn, seeking="volunteer", limit=6)["items"]


def _s_engagements(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return relationships.mine(conn, org_id=org_id, status="active", direction="out", limit=15)


def _s_profile(conn: Connection, *, org_id: str, user_id: str | None, **_: Any) -> Any:
    from . import profiles
    return {"org": profiles.of_owner(conn, org_id=org_id),
            "person": profiles.of_owner(conn, user_id=user_id) if user_id else None}


def _s_credentials(conn: Connection, *, org_id: str, user_id: str | None, **_: Any) -> Any:
    if not user_id:
        return {"credentials": [], "experiences": []}
    return {
        "credentials": conn.query(
            "SELECT id::text AS id, council, council_code, uf, verification_status, valid_until, revoked_at"
            " FROM professional_credentials WHERE user_id = $1 ORDER BY council", user_id),
        "experiences": conn.query(
            "SELECT id::text AS id, role, org_name, started_on, ended_on, state, visibility"
            " FROM professional_experiences WHERE user_id = $1 ORDER BY started_on DESC LIMIT 20", user_id),
    }


def _s_territory(conn: Connection, *, org_id: str, **_: Any) -> Any:
    """Para o poder público: necessidades declaradas do território, com a fonte de cada número."""
    uf = conn.scalar("SELECT uf FROM organizations WHERE id = $1", org_id)
    return conn.query(
        # a coluna é `cause` (e `ods`), não `theme`; `beneficiary_groups` é atributo da NECESSIDADE, nunca de
        # pessoa — a política de uso do termo em taxonomy_terms proíbe usá-lo para filtrar gente.
        "SELECT id::text AS id, territory, cause, ods, beneficiary_groups, title, description,"
        " people_estimate, source_name, source_url, source_date, priority, status, created_at"
        " FROM territory_needs"
        " WHERE ($1::text IS NULL OR territory = $1 OR territory LIKE 'BR-' || $1 || '%')"
        " ORDER BY priority DESC, created_at DESC LIMIT 20", uf)


def _s_programs(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return conn.query(
        "SELECT id::text AS id, title, instrument, status, opens_at, closes_at, budget_total_cents,"
        " managed_on_platform FROM calls WHERE owner_org_id = $1 ORDER BY coalesce(closes_at, opens_at) DESC"
        " NULLS LAST LIMIT 15", org_id)


def _s_monitored(conn: Connection, *, org_id: str, **_: Any) -> Any:
    """Projetos que este órgão acompanha: por relação ativa ou por candidatura ao próprio edital."""
    return conn.query(
        "SELECT DISTINCT p.id::text AS id, p.title, p.status, p.territory,"
        " coalesce(o.trade_name, o.legal_name) AS org_name,"
        " (SELECT committed_cents FROM project_funding(p.id)) AS committed_cents"
        " FROM projects p JOIN organizations o ON o.id = p.org_id"
        " WHERE EXISTS (SELECT 1 FROM relationships r WHERE r.target_project_id = p.id"
        "                 AND r.source_org_id = $1 AND r.status = 'active')"
        "    OR EXISTS (SELECT 1 FROM applications a JOIN calls c ON c.id = a.call_id"
        "                 WHERE a.project_id = p.id AND c.owner_org_id = $1)"
        " ORDER BY 2 LIMIT 20", org_id)


def _s_indicators(conn: Connection, *, org_id: str, **_: Any) -> Any:
    """Indicadores VALIDADOS de projetos publicados no território. Medição não validada não entra em painel público."""
    uf = conn.scalar("SELECT uf FROM organizations WHERE id = $1", org_id)
    return conn.query(
        "SELECT ic.code, ic.name, ic.unit, count(DISTINCT pi.project_id) AS projects,"
        " sum(v.value) FILTER (WHERE v.status = 'validated') AS validated_sum"
        " FROM project_indicators pi JOIN indicator_catalog ic ON ic.id = pi.indicator_id"
        " JOIN projects p ON p.id = pi.project_id"
        " LEFT JOIN indicator_values v ON v.project_indicator_id = pi.id"
        " WHERE p.visibility = 'published'"
        "   AND ($1::text IS NULL OR p.territory = $1 OR p.territory LIKE 'BR-' || $1 || '%')"
        " GROUP BY ic.code, ic.name, ic.unit ORDER BY 4 DESC NULLS LAST LIMIT 20", uf)


def _s_moderation(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return {
        "open_reports": int(conn.scalar(
            "SELECT count(*) FROM reports WHERE status IN ('open','triage','investigating')") or 0),
        "recent_actions": conn.query(
            "SELECT id::text AS id, measure, rule_ref, created_at, ends_at, status FROM enforcement_actions"
            " ORDER BY created_at DESC LIMIT 10"),
    }


def _s_queues(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return {
        "documents": int(conn.scalar("SELECT count(*) FROM documents WHERE status = 'in_review'"
                                     " AND deleted_at IS NULL") or 0),
        "orgs": int(conn.scalar("SELECT count(*) FROM organizations WHERE compliance_status = 'in_review'") or 0),
        "credentials": int(conn.scalar("SELECT count(*) FROM professional_credentials"
                                       " WHERE verification_status = 'pending'") or 0),
        "impact_updates": int(conn.scalar("SELECT count(*) FROM impact_updates"
                                          " WHERE status IN ('submitted','under_review')") or 0),
    }


def _s_platform(conn: Connection, *, org_id: str, **_: Any) -> Any:
    return {
        "organizations": int(conn.scalar("SELECT count(*) FROM organizations") or 0),
        "projects_published": int(conn.scalar("SELECT count(*) FROM projects"
                                              " WHERE visibility = 'published'") or 0),
        "listings_published": int(conn.scalar("SELECT count(*) FROM marketplace_listings"
                                              " WHERE publication_state = 'published'") or 0),
        "relationships_active": int(conn.scalar("SELECT count(*) FROM relationships"
                                                " WHERE status = 'active'") or 0),
        "proposals_open": int(conn.scalar("SELECT count(*) FROM proposals"
                                          " WHERE status IN ('sent','viewed','in_review')") or 0),
        "events_24h": int(conn.scalar("SELECT count(*) FROM domain_events"
                                      " WHERE at > now() - interval '24 hours'") or 0),
    }


_SECTIONS = {
    "next_actions": _s_next_actions, "readiness": _s_readiness, "proposals_in": _s_proposals_in,
    "proposals_out": _s_proposals_out, "projects": _s_projects, "listings": _s_listings,
    "reports_due": _s_reports_due, "conversations": _s_conversations, "network": _s_network,
    "pipeline": _s_pipeline, "supported": _s_supported, "reports_to_review": _s_reports_to_review,
    "discover": _s_discover, "opportunities": _s_opportunities, "engagements": _s_engagements,
    "profile": _s_profile, "credentials": _s_credentials, "territory": _s_territory, "programs": _s_programs,
    "monitored": _s_monitored, "indicators": _s_indicators, "moderation": _s_moderation, "queues": _s_queues,
    "platform": _s_platform,
}
