"""Dados de DEMONSTRAÇÃO — exclusivamente para development/test (bloqueado em staging/production por config.validate).

Tudo aqui é FICTÍCIO e marcado como tal (``is_example = true`` e prefixo "[EXEMPLO FICTÍCIO]" nos editais). CNPJs são
gerados apenas com dígitos verificadores válidos para passar na validação de formato — não pertencem a organizações reais.
Senha padrão: variável DEMO_PASSWORD (padrão "Demo-Impacto-2026!") — nunca usar fora do ambiente local.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from .db.pool import DbContext
from .db.pq import Json
from .security import passwords
from .services.validators import cnpj_with_check_digits

DEMO_EMAILS = {"osc": "osc@demo.impacto.local", "company": "empresa@demo.impacto.local",
               "provider": "contador@demo.impacto.local", "government": "governo@demo.impacto.local",
               "admin": "admin@demo.impacto.local"}


def seed(state, force: bool = False) -> dict:
    s = state.settings
    if s.env not in ("development", "test"):
        raise RuntimeError("seed de demonstração bloqueado fora de development/test")
    pw = os.getenv("DEMO_PASSWORD", "Demo-Impacto-2026!")
    h = passwords.hash_password(pw)
    now = datetime.now(timezone.utc)
    with state.pool.tx(DbContext(system=True)) as c:
        if c.scalar("SELECT count(*) FROM users WHERE email = $1", DEMO_EMAILS["osc"]):
            return {"status": "already_seeded"}

        def org(kind, name, base, uf="MT", ibge="5105259", **kw):
            oid = c.scalar("INSERT INTO organizations(kind, legal_name, cnpj, uf, city, ibge_code, founded_on, description, causes, ods,"
                           " certifications, compliance_status) VALUES ($1,$2,$3,$4,$5,$6,$7::date,$8,$9::text[],$10::smallint[],$11::text[],$12)"
                           " RETURNING id::text", kind, name, cnpj_with_check_digits(base), uf, kw.get("city", "Lucas do Rio Verde"), ibge,
                           kw.get("founded", "2015-03-10"), kw.get("desc", "Organização fictícia para demonstração."), kw.get("causes", []),
                           kw.get("ods", []), kw.get("certs", []), kw.get("compliance", "approved"))
            return oid

        def user(email, name, oid, admin=False):
            uid = c.scalar("INSERT INTO users(email, full_name, password_hash, email_verified_at, is_platform_admin) VALUES ($1,$2,$3, now(), $4::bool)"
                           " RETURNING id::text", email, name, h, admin)
            c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'owner')", uid, oid)
            return uid

        osc = org("osc", "Instituto Exemplo Fictício de Música e Cidadania", "990000000001", causes=["cultura", "educacao", "criancas_adolescentes"],
                  ods=[4, 10], certs=["registro_cmdca"], desc="OSC fictícia: oficinas de música para crianças e adolescentes.")
        comp = org("company", "Empresa Exemplo Fictícia S.A.", "990000000002", uf="SP", ibge="3550308", city="São Paulo")
        prov = org("provider", "Contabilidade Exemplo Fictícia Ltda.", "990000000003")
        gov = org("government", "Secretaria Municipal Exemplo (fictícia)", "990000000004")
        plat = c.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1") or \
            c.scalar("INSERT INTO organizations(kind, legal_name, compliance_status) VALUES ('platform','Administração da Plataforma','approved') RETURNING id::text")
        u_osc = user(DEMO_EMAILS["osc"], "Ana Exemplo (OSC)", osc)
        u_comp = user(DEMO_EMAILS["company"], "Bruno Exemplo (Empresa)", comp)
        u_prov = user(DEMO_EMAILS["provider"], "Carla Exemplo (Contadora)", prov)
        user(DEMO_EMAILS["government"], "Davi Exemplo (Governo)", gov)
        user(DEMO_EMAILS["admin"], "Admin Demo", plat, admin=True)
        c.run("INSERT INTO funder_profiles(org_id, causes, ods, territories, ticket_min_cents, ticket_max_cents, required_document_types, min_org_age_months)"
              " VALUES ($1,'{educacao,cultura}','{4}','{BR-MT}', 100000, 5000000, '{estatuto_social}', 24)", comp)
        c.run("INSERT INTO provider_profiles(org_id, services, categories, territories) VALUES ($1,'{Prestação de contas,Contabilidade para OSC}',"
              " '{contador}','{BR-MT}')", prov)
        c.run("INSERT INTO professional_credentials(org_id, user_id, council, number, uf, holder_name, verification_status, verification_note, verified_at)"
              " VALUES ($1,$2,'CRC','MT-000000/O-0','MT','Carla Exemplo','verified','Credencial FICTÍCIA de demonstração', now())", prov, u_prov)
        calls = [
            ("private", "grant", "Empresa Exemplo Fictícia S.A.", "[EXEMPLO FICTÍCIO] Programa Música nas Escolas", ["cultura", "educacao"], ["BR-MT"],
             100000, 2000000, comp, True),
            ("federal", "edital", "Ministério Exemplo (fictício)", "[EXEMPLO FICTÍCIO] Edital Nacional de Cultura Comunitária", ["cultura"], ["BR"],
             500000, 10000000, None, False),
            ("state", "fund", "Fundo Estadual Exemplo (fictício)", "[EXEMPLO FICTÍCIO] Fundo Estadual da Infância", ["criancas_adolescentes"], ["BR-MT"],
             200000, 3000000, None, False),
            ("municipal", "edital", "Secretaria Municipal Exemplo (fictícia)", "[EXEMPLO FICTÍCIO] Chamamento Público Esporte e Lazer", ["esporte"],
             ["BR-MT-5105259"], 50000, 800000, gov, True),
            ("international", "grant", "Fundação Internacional Exemplo (fictícia)", "[EXEMPLO FICTÍCIO] Global Youth Grant", ["juventude", "educacao"],
             ["INT"], 1000000, 20000000, None, False),
        ]
        for sphere, inst, funder, title, causes, terr, tmin, tmax, owner, managed in calls:
            c.run("INSERT INTO calls(owner_org_id, source_type, sphere, instrument, funder_name, title, summary, url, causes, territories, ticket_min_cents,"
                  " ticket_max_cents, required_document_types, min_org_age_months, requirements, opens_at, closes_at, status, managed_on_platform, is_example)"
                  " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::text[],$10::text[],$11::bigint,$12::bigint,'{estatuto_social,cnd_federal}',24,$13::jsonb,$14,$15,'open',$16::bool,true)",
                  owner, "platform" if owner == comp else ("government" if owner == gov else "curated"), sphere, inst, funder, title,
                  "Oportunidade FICTÍCIA para demonstração da plataforma. Não se candidate fora do ambiente de testes.",
                  None if owner else "https://example.org/edital-ficticio", causes, terr, tmin, tmax,
                  Json([{"code": "plano_trabalho", "label": "Plano de trabalho no modelo do edital", "mandatory": True}]),
                  now - timedelta(days=5), now + timedelta(days=40), managed)
        pid = c.scalar("INSERT INTO projects(org_id, title, summary, problem, objectives, causes, ods, territory, beneficiaries_count, urgency, indicators,"
                       " starts_on, ends_on, created_by) VALUES ($1,'Orquestra Comunitária Exemplo','Aulas coletivas de violão para 40 crianças (dados fictícios).',"
                       " 'Falta de acesso a educação musical no bairro (exemplo).','Formar 40 crianças em 12 meses.', '{cultura,educacao}','{4}','BR-MT-5105259',40,'high',"
                       " $2::jsonb, current_date + 30, current_date + 395, $3) RETURNING id::text", osc,
                       Json([{"name": "Crianças com frequência ≥ 75%", "unit": "crianças", "baseline": 0, "target": 32}]), u_osc)
        c.run("INSERT INTO budget_items(project_id, org_id, description, category, quantity, unit_cost_cents) VALUES ($1,$2,'Violões',"
              " 'equipment', 10, 50000), ($1,$2,'Professor de música (12 meses)','personnel', 12, 150000)", pid, osc)
        c.run("INSERT INTO milestones(project_id, org_id, seq, title, amount_cents, due_on, status) VALUES ($1,$2,1,'Compra dos instrumentos',500000,"
              " current_date + 45,'open'), ($1,$2,2,'Aulas — 1º semestre',900000, current_date + 210,'open'), ($1,$2,3,'Aulas — 2º semestre',900000,"
              " current_date + 395,'open')", pid, osc)
        c.run("UPDATE projects SET visibility = 'published', status = 'published', published_at = now() WHERE id = $1", pid)
        pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        import hashlib, uuid as _uuid
        for dt, title, valid in (("estatuto_social", "Estatuto social (exemplo)", None), ("cartao_cnpj", "Cartão CNPJ (exemplo)", None),
                                 ("ata_eleicao_diretoria", "Ata de eleição (exemplo)", now.date() + timedelta(days=500)),
                                 ("cnd_federal", "CND federal (exemplo)", now.date() + timedelta(days=150))):
            key = f"{osc}/{_uuid.uuid4().hex}"
            state.storage.put(key, pdf, "application/pdf")
            c.run("INSERT INTO documents(org_id, doc_type, title, filename, mime_type, size_bytes, sha256, storage_key, status, valid_until, uploaded_by)"
                  " VALUES ($1,$2,$3,$4,'application/pdf',$5::bigint,$6,$7,'pending_scan',$8::date,$9)",
                  osc, dt, title, dt + ".pdf", len(pdf), hashlib.sha256(pdf).hexdigest(), key, valid, u_osc)
        c.run("INSERT INTO materials(org_id, title, summary, category, url, status, published_at) VALUES ($1,'[EXEMPLO] Guia de prestação de contas',"
              " 'Material fictício de demonstração.','guide','https://example.org/guia-ficticio','published', now())", gov)
        _seed_solutions(c, osc, u_osc)
    return {"status": "seeded", "password_env": "DEMO_PASSWORD", "users": DEMO_EMAILS}


# Soluções de DEMONSTRAÇÃO (is_demo = true; só em development/test). Todas fictícias, autodeclaradas, sem evidência verificada.
_DEMO_SOLUTIONS = [
    ("project", "running", "[DEMO] Oficinas de arte em CAPS", "Oficinas semanais de artes plásticas e música para usuários de um Centro de Atenção Psicossocial (exemplo fictício).",
     ["saude", "cultura"], ["saude_mental"], ["caps"], [3, 10], "MT", 4500000, True),
    ("project", "running", "[DEMO] Arteterapia comunitária", "Grupos de arteterapia para pessoas em sofrimento psíquico, em parceria com a rede de saúde mental (exemplo fictício).",
     ["saude", "cultura"], ["saude_mental"], [], [3], "SP", 2500000, False),
    ("project", "proposal", "[DEMO] Convivência ativa para idosos", "Grupos de convivência e atividade física para pessoas idosas no território (exemplo fictício).",
     ["pessoa_idosa", "saude"], ["idosos"], [], [3, 10], "MT", 1800000, False),
    ("project", "running", "[DEMO] Escola do campo conectada", "Educação rural com transporte escolar e conteúdos adaptados à realidade do campo (exemplo fictício).",
     ["educacao"], ["rural", "criancas"], [], [4], "PA", 9000000, False),
    ("project", "running", "[DEMO] Rede de acolhimento a mulheres", "Acolhimento e orientação jurídica para mulheres em situação de violência doméstica (exemplo fictício).",
     ["igualdade_genero", "direitos_humanos"], ["mulheres", "violencia_mulheres"], [], [5, 16], "BA", 6000000, False),
    ("social_tech", "running", "[DEMO] Tecnologia assistiva para PcD", "Oficinas de tecnologia assistiva e acessibilidade digital para pessoas com deficiência (exemplo fictício).",
     ["pessoa_com_deficiencia", "inclusao_digital"], ["pcd"], [], [9, 10], "RS", 3000000, False),
    ("idea", "idea", "[DEMO] Biblioteca móvel ribeirinha", "Ideia de embarcação adaptada com acervo rotativo para comunidades ribeirinhas sem biblioteca (exemplo fictício, não executada).",
     ["educacao", "cultura"], ["rural"], [], [4], "AM", None, False),
]


def _seed_solutions(c, osc_org: str, user: str) -> None:
    for kind, stage, title, summary, themes, pop, inst, ods, uf, budget, fund in _DEMO_SOLUTIONS:
        c.run("INSERT INTO solutions(org_id, created_by, kind, stage, title, summary, problem, approach, themes, population, institutions, ods, uf, budget_cents,"
              " seeking_funding, needed_cents, license, allow_replication, allow_adaptation, visibility, is_demo, source_type, source_name, ownership_type, authorization_publish, rights_holder)"
              " VALUES ($1,$2,$3,$4,$5,$6,'Problema descrito de forma fictícia para demonstração.','Abordagem fictícia para demonstração.',$7::text[],$8::text[],$9::text[],"
              " $10::smallint[],$11,$12::bigint,$13::bool,$14::bigint,$15,$16::bool,$16::bool,'published',true,'author','Dados de demonstração','organization',true,'DEMO')",
              osc_org, user, kind, stage, title, summary, themes, pop, inst, ods, uf, budget, fund, int(budget * 0.5) if fund and budget else None,
              "cc_by" if fund else "all_rights_reserved", bool(fund))
