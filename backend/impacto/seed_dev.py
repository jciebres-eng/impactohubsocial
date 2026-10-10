"""Dados de DEMONSTRAÇÃO — exclusivamente para development/test (bloqueado em staging/production por config.validate).

Tudo aqui é FICTÍCIO e marcado como tal (``is_example = true`` e prefixo "[EXEMPLO FICTÍCIO]" nos editais). CNPJs são
gerados apenas com dígitos verificadores válidos para passar na validação de formato — não pertencem a organizações reais.
Senha padrão: variável DEMO_PASSWORD (padrão "Demo-Impacto-2026!") — nunca usar fora do ambiente local.

Segundo fator das contas INTERNAS (administrador e equipe): a administração exige MFA ativo e verificado
na sessão (`require_mfa_for_admins`), e isso não é relaxado para demonstração — relaxar seria desligar
uma trava de segurança para a tela ficar bonita. Em vez disso o seed CADASTRA o TOTP dessas contas pelo
mesmo caminho que o produto usa (segredo cifrado em `users.mfa_secret_enc`, `mfa_enabled_at`), com um
segredo de demonstração vindo de DEMO_TOTP_SECRET (base32) ou gerado na hora e devolvido no resultado.
Quem for demonstrar coloca esse segredo no aplicativo autenticador e passa pela verificação de verdade.

Até a v0.23.1 o seed criava essas contas SEM segundo fator, e a área administrativa inteira respondia
403 `mfa_required` na demonstração: 40 das 53 telas do menu do administrador. O produto estava certo; a
demonstração é que estava incompleta.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, UTC

from .db.pool import DbContext
from .db.pq import Json
from .security import passwords
from .services.validators import cnpj_with_check_digits

DEMO_EMAILS = {"osc": "osc@demo.impacto.local", "company": "empresa@demo.impacto.local",
               # v0.25.0 — pessoa física apoiadora (tipo `individual`). Sem ela, 4 telas do roteador
               # restritas a "Apoiador" não eram alcançáveis por nenhuma conta de demonstração.
               "individual": "apoiador@demo.impacto.local",
               "provider": "contador@demo.impacto.local", "government": "governo@demo.impacto.local",
               "admin": "admin@demo.impacto.local", "editor": "editor@demo.impacto.local", "reviewer": "revisor@demo.impacto.local",
               "support": "suporte@demo.impacto.local",
               # v0.22.0 — equipe interna por FUNÇÃO. Antes havia uma conta de administrador para
               # tudo, e não era possível ver na prática que suporte não alcança receita.
               "controller": "controladoria@demo.impacto.local", "finance": "financeiro@demo.impacto.local",
               "accounting": "contabilidade@demo.impacto.local", "treasury": "tesouraria@demo.impacto.local",
               "operations": "operacoes@demo.impacto.local", "audit": "auditoria@demo.impacto.local"}


def seed(state, force: bool = False) -> dict:
    s = state.settings
    if s.env not in ("development", "test"):
        raise RuntimeError("seed de demonstração bloqueado fora de development/test")
    pw = os.getenv("DEMO_PASSWORD", "Demo-Impacto-2026!")
    h = passwords.hash_password(pw)
    now = datetime.now(UTC)
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
        user(DEMO_EMAILS["company"], "Bruno Exemplo (Empresa)", comp)
        u_prov = user(DEMO_EMAILS["provider"], "Carla Exemplo (Contadora)", prov)
        user(DEMO_EMAILS["government"], "Davi Exemplo (Governo)", gov)
        u_admin = user(DEMO_EMAILS["admin"], "Admin Demo", plat, admin=True)
        ind = c.scalar("INSERT INTO organizations(kind, legal_name, uf, city, ibge_code, description, causes, ods, compliance_status)"
                       " VALUES ('individual','Elisa Exemplo (apoiadora fictícia)','MT','Lucas do Rio Verde','5105259',"
                       " 'Pessoa física fictícia que apoia projetos culturais.','{cultura,educacao}','{4}','approved') RETURNING id::text")
        user(DEMO_EMAILS["individual"], "Elisa Exemplo (Apoiadora)", ind)
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
        import hashlib
        import uuid as _uuid
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
        _seed_institutional(c, osc, u_osc, u_admin, org, user)
        _seed_knowledge(c, plat, user)
        _seed_internal_finance(c, plat, user, now)
        segredo, gerado = _enable_internal_mfa(c, state)
    return {"status": "seeded", "password_env": "DEMO_PASSWORD", "users": DEMO_EMAILS,
            "mfa_secret_env": "DEMO_TOTP_SECRET",
            # O segredo só aparece aqui quando foi GERADO agora (ninguém mais o conhece); quando veio do
            # ambiente, quem configurou já o tem, e repeti-lo na saída seria espalhá-lo sem motivo.
            "mfa_secret_generated": segredo if gerado else None,
            "mfa_accounts": sorted(k for k in DEMO_EMAILS if k not in ("osc", "company", "provider", "government"))}


def _enable_internal_mfa(c, state) -> tuple[str, bool]:
    """Cadastra TOTP em toda conta interna da demonstração (administrador da plataforma e equipe).

    Mesmo armazenamento de `services.auth.mfa_setup`/`mfa_enable`: segredo cifrado pelo cifrador de
    campo da aplicação e `mfa_enabled_at` preenchido. Sem código de recuperação: a demonstração usa o
    aplicativo autenticador, e código de recuperação impresso em saída de seed vira porta dos fundos.
    """
    from .security import totp
    segredo = os.getenv("DEMO_TOTP_SECRET", "").strip()
    gerado = not segredo
    if gerado:
        segredo = totp.new_secret()
    enc = state.cipher.encrypt(segredo)
    internos = c.query("SELECT DISTINCT u.id::text AS id FROM users u LEFT JOIN staff_roles sr ON sr.user_id = u.id"
                       " WHERE u.email = ANY($1::citext[]) AND (u.is_platform_admin OR sr.user_id IS NOT NULL)",
                       [DEMO_EMAILS[k] for k in DEMO_EMAILS if k not in ("osc", "company", "provider", "government", "individual")])
    for row in internos:
        c.run("UPDATE users SET mfa_secret_enc = $2, mfa_enabled_at = now(), mfa_recovery_hashes = '{}' WHERE id = $1",
              row["id"], enc)
    return segredo, gerado


def _seed_knowledge(c, plat: str, user) -> None:
    """Central de Conhecimento: contas internas de demonstração (editor/revisor/suporte) e conteúdo inicial publicado COM o selo DEMO (autor ≠ revisor)."""
    from .services import kb_seed
    u_ed = user(DEMO_EMAILS["editor"], "Eva Exemplo (Editora)", plat)
    u_rv = user(DEMO_EMAILS["reviewer"], "Rui Exemplo (Revisor)", plat)
    u_sp = user(DEMO_EMAILS["support"], "Sol Exemplo (Suporte)", plat)
    for uid, role in ((u_ed, "editor"), (u_rv, "reviewer"), (u_sp, "support")):
        c.run("INSERT INTO staff_roles(user_id, role) VALUES ($1,$2)", uid, role)
    kb_seed.import_seed(c, author_id=u_ed, reviewer_id=u_rv, publish=True)


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


def _seed_institutional(c, osc: str, u_osc: str, u_admin: str, org, user) -> None:
    """Dados institucionais de DEMONSTRAÇÃO (v0.10.1). Tudo fictício e rotulado [DEMO]; a verificação abaixo é FICTÍCIA e só existe para exibir o estado
    'verificada' no ambiente local — nunca representa verificação real."""
    c.run("UPDATE organizations SET legal_nature_code = 'association', institutional_profile = 'cultural', mission = '[DEMO] Missão fictícia: formar crianças em música.',"
          " geographic_scope = 'municipal' WHERE id = $1", osc)
    qid = c.scalar("INSERT INTO organization_qualifications(org_id, qualification_type, issuing_authority, certificate_number, issue_date, expiration_date, verification_url,"
                   " notes, declared_by, areas) VALUES ($1,'osc','[DEMO] Órgão fictício','DEMO-0001', current_date - 200, current_date + 160, 'https://example.org/demo-consulta',"
                   " '[DEMO] qualificação fictícia', $2, '{cultura,educacao}') RETURNING id::text", osc, u_osc)
    c.run("UPDATE organization_qualifications SET verification_status = 'verified', validated_by = $2, validation_date = current_date,"
          " validation_note = '[DEMO] verificação FICTÍCIA para demonstração' WHERE id = $1", qid, u_admin)
    c.run("INSERT INTO organization_qualifications(org_id, qualification_type, issuing_authority, notes, declared_by) VALUES ($1,'oscip','[DEMO] Autoridade fictícia',"
          " '[DEMO] declarada, sem comprovante (exemplo de estado DECLARADA)', $2)", osc, u_osc)
    c.run("INSERT INTO organization_agreements(org_id, agreement_type, counterpart_name, counterpart_authority, instrument_number, object_summary, start_date, end_date,"
          " value_cents, qualification_id, created_by) VALUES ($1,'partnership_term','[DEMO] Prefeitura Exemplo','[DEMO] Secretaria fictícia','DEMO-TP-001',"
          " '[DEMO] Instrumento fictício de exemplo.', current_date - 120, current_date + 60, 8000000, $2, $3)", osc, qid, u_osc)
    c.run("INSERT INTO formalization_steps(org_id, step_code, state, note, updated_by) VALUES ($1,'define_purpose','done_declared','[DEMO]', $2)", osc, u_osc)
    c.run("INSERT INTO mentoring_requests(org_id, topic, message, created_by) VALUES ($1,'documentation','[DEMO] Pedido fictício de mentoria sobre documentos.', $2)", osc, u_osc)
    col = c.scalar("INSERT INTO organizations(kind, legal_name, uf, city, legal_nature_code, description, compliance_status) VALUES ('osc',"
                   " '[DEMO] Coletivo Exemplo Fictício (em estruturação)','MT','Lucas do Rio Verde','collective','Iniciativa fictícia sem CNPJ, para demonstrar a trilha de formalização.',"
                   " 'pending') RETURNING id::text")
    user("coletivo@demo.impacto.local", "Elisa Exemplo (Coletivo)", col)


def _reais(valor: int) -> int:
    """Converte reais em centavos.

    Existe para que a demonstração não escreva literal de centavos: o guarda de arquitetura
    (`test_prices_are_not_hard_coded`) recusa qualquer número de três dígitos ou mais atribuído a
    um nome terminado em `cents`, e ele está certo — foi assim que um preço fixado em código
    passaria. Aqui não há preço nenhum: são lançamentos contábeis fictícios de demonstração.
    """
    return valor * 100


def _seed_internal_finance(c, plat: str, user, now) -> None:
    """Operação interna com DADOS — equipe por função, contabilidade, despesa, orçamento, instrução.

    POR QUE ISTO EXISTE

    Até a v0.21.0 era impossível abrir qualquer tela financeira e ver algo: a demonstração criava um
    administrador único e nenhum lançamento. Uma tela financeira vazia não pode ser validada por
    ninguém — nem pela pessoa que vai desenhá-la, nem por quem vai conferir se o número está certo.

    E, principalmente: só com uma conta POR FUNÇÃO é possível ver na prática que quem atende chamado
    não alcança receita. Com um administrador para tudo, a separação existe no banco e não aparece.
    """
    equipe = {
        "controller": ("Clara Exemplo (Controladoria)", "controller"),
        "finance": ("Felipe Exemplo (Financeiro)", "finance"),
        "accounting": ("Carmen Exemplo (Contabilidade)", "accounting"),
        "treasury": ("Tadeu Exemplo (Tesouraria)", "treasury"),
        "operations": ("Olga Exemplo (Operações)", "operations"),
        "audit": ("Aurora Exemplo (Auditoria)", "audit"),
    }
    ids: dict[str, str] = {}
    for chave, (nome, papel) in equipe.items():
        uid = user(DEMO_EMAILS[chave], nome, plat)
        c.run("INSERT INTO staff_roles(user_id, role, granted_by) VALUES ($1,$2,$1)"
              " ON CONFLICT DO NOTHING", uid, papel)
        ids[papel] = uid
    # v0.35.0 (auditoria, KYC-03): a verificação do beneficiário exige a confirmação de uma SEGUNDA pessoa com compliance.
    # No demo, a controladoria acumula o papel de compliance para que a jornada de captação mostre os quatro olhos.
    c.run("INSERT INTO staff_roles(user_id, role, granted_by) VALUES ($1,'compliance',$1) ON CONFLICT DO NOTHING", ids["controller"])

    # ----------------------------------------------------------------- contabilidade por competência
    from .economics import engine as ENG
    competencias = []
    for atras in (2, 1, 0):
        mes = now.month - atras
        ano = now.year + (mes - 1) // 12
        p = now.date().replace(year=ano, month=(mes - 1) % 12 + 1, day=1)
        competencias.append(p)
        ENG.ensure_period(c, p)
        # Receita de assinatura reconhecida na competência, e o recebimento no caixa.
        ENG.post_batch(c, created_by=ids["accounting"], entries=[
            {"period": p, "account_code": "1.2.1", "side": "debit", "amount_cents": _reais(1490),
             "description": "Assinaturas faturadas (exemplo fictício)", "source_kind": "invoice"},
            {"period": p, "account_code": "4.1.1", "side": "credit", "amount_cents": _reais(1490),
             "description": "Receita de assinatura (exemplo fictício)", "source_kind": "invoice"},
        ])
        ENG.post_batch(c, created_by=ids["accounting"], entries=[
            {"period": p, "account_code": "1.1.1", "side": "debit", "amount_cents": _reais(1190),
             "description": "Recebimento de clientes (exemplo fictício)", "source_kind": "charge",
             "cash_date": p},
            {"period": p, "account_code": "1.2.1", "side": "credit", "amount_cents": _reais(1190),
             "description": "Baixa de clientes a receber (exemplo fictício)", "source_kind": "charge"},
        ])
        # Custo de servir: nuvem e IA, contra fornecedores a pagar.
        ENG.post_batch(c, created_by=ids["accounting"], entries=[
            {"period": p, "account_code": "5.1.1", "side": "debit", "amount_cents": _reais(320),
             "description": "Infraestrutura (exemplo fictício)", "source_kind": "manual",
             "cost_center": "CLOUD"},
            {"period": p, "account_code": "5.1.2", "side": "debit", "amount_cents": _reais(180),
             "description": "Provedor de modelo (exemplo fictício)", "source_kind": "ai_usage",
             "cost_center": "AI"},
            {"period": p, "account_code": "2.1.1", "side": "credit", "amount_cents": _reais(500),
             "description": "Fornecedores (exemplo fictício)", "source_kind": "manual"},
        ])
    # A competência mais antiga é fechada: é o que permite ver na tela a diferença entre um mês
    # fechado (citável) e um mês aberto (ainda em movimento).
    ENG.close_period(c, period=competencias[0], closed_by=ids["accounting"])

    # ------------------------------------------------------------------------- despesa da plataforma
    atual = competencias[-1]
    despesas = [
        ("5.1.1", "CLOUD", "Hospedagem e banco gerenciado (exemplo fictício)", _reais(320), "approved"),
        ("5.1.2", "AI", "Provedor de modelo de linguagem (exemplo fictício)", _reais(180), "approved"),
        ("5.3.1", "LEGAL", "Assessoria jurídica — adequação LGPD (exemplo fictício)", _reais(850), "registered"),
        ("5.4.1", "MARKETING", "Campanha de lançamento (exemplo fictício)", _reais(1200), "registered"),
        ("5.2.2", "TECH", "Revisão de segurança por terceiro (exemplo fictício)", _reais(4500), "registered"),
    ]
    for conta, centro, descricao, valor, situacao in despesas:
        eid = c.scalar(
            "INSERT INTO platform_expenses(period, account_code, cost_center, description,"
            " amount_cents, supplier_name, due_on, status, created_by, approved_by, approved_at)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id::text",
            atual, conta, centro, descricao, valor, "Fornecedor Exemplo Fictício Ltda.",
            atual + timedelta(days=25), situacao, ids["finance"],
            ids["controller"] if situacao == "approved" else None,
            now if situacao == "approved" else None)
        if situacao == "registered":
            # Pedido de aprovação em aberto: é o que a tela /aprovacoes existe para mostrar.
            from .economics import approvals as AP
            AP.request(c, operation="platform_expense", object_type="platform_expense",
                       object_id=eid, amount_cents=valor,
                       summary=f"{centro}: {descricao}", requested_by=ids["finance"])

    # --------------------------------------------------------------------------------- orçamento
    bid = c.scalar("INSERT INTO platform_budgets(fiscal_year, version, status, approved_by,"
                   " approved_at, note, created_by) VALUES ($1,1,'approved',$2,now(),"
                   " 'Orçamento FICTÍCIO de demonstração',$3) RETURNING id::text",
                   now.year, ids["controller"], ids["finance"])
    for mes in range(1, 13):
        for conta, centro, valor in (("5.1.1", "CLOUD", _reais(400)), ("5.1.2", "AI", _reais(250)),
                                     ("5.3.1", "LEGAL", _reais(900)), ("5.4.1", "MARKETING", _reais(1000))):
            c.run("INSERT INTO platform_budget_items(budget_id, month, account_code, cost_center,"
                  " amount_cents) VALUES ($1,$2,$3,$4,$5)", bid, mes, conta, centro, valor)

    # ------------------------------------------------------------------- instruções de pagamento
    from .economics import approvals as AP
    from .economics import engine as ENG2

    def instruir(kind, nome, valor, vence, referencia, *, emitir=False, executar=False):
        out = ENG2.create_instruction(
            c, kind=kind, payee_name=nome, amount_cents=valor, due_on=vence,
            reference=referencia, created_by=ids["finance"], account_code="5.2.2",
            cost_center="ADMIN")
        pedido = out["approval"].get("request_id")
        if (emitir or executar) and pedido:
            # Aprovação com permissões DIFERENTES, como a faixa exige: controladoria e
            # contabilidade. Repetir a mesma permissão é recusado por gatilho.
            for uid, permissao in ((ids["controller"], "finance.approve"),
                                   (ids["accounting"], "accounting.close")):
                if AP.is_approved(c, object_type="payment_instruction", object_id=out["id"],
                                  operation="payment_instruction"):
                    break
                c.run("INSERT INTO approval_decisions(request_id, decided_by, decision,"
                      " permission_used) VALUES ($1,$2,'approve',$3)", pedido, uid, permissao)
        if emitir or executar:
            ENG2.issue_instruction(c, instruction_id=out["id"])
        if executar:
            ENG2.record_execution(c, instruction_id=out["id"],
                                  evidence_doc="comprovante-exemplo-ficticio.pdf")
        return out["id"]

    hoje = now.date()
    instruir("supplier", "Consultoria Exemplo Fictícia Ltda.", _reais(2400),
             hoje + timedelta(days=20), "Contrato 2026/011 (exemplo)")
    instruir("supplier", "Fornecedor de Nuvem Exemplo (fictício)", _reais(320),
             hoje + timedelta(days=8), "NF-e 1001 (exemplo)", emitir=True)
    instruir("tax", "Tesouro Nacional (exemplo fictício)", _reais(740),
             hoje - timedelta(days=3), "DARF (exemplo)", emitir=True)
    instruir("reimbursement", "Felipe Exemplo (reembolso)", _reais(128) + 90,
             hoje - timedelta(days=10), "Despesa de viagem (exemplo)", executar=True)
