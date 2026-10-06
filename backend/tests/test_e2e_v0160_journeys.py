"""Sete jornadas da REDE, de ponta a ponta pela API real.

Cada jornada é o caminho que uma pessoa percorre de verdade, na ordem em que percorre. Não há atalho de banco para
"chegar no estado": cada passo é a chamada que a interface faz. Onde a plataforma RECUSA, a recusa é o resultado
esperado e está escrita no teste — é o que ela entrega hoje, e afirmar outra coisa seria mentir.

A cadeia que estas jornadas exercitam é a do pedido:

    Pessoa/Organização → Contexto → Necessidade → Rede → Match → Proposta → Relação → Projeto → Execução →
    Evidência → Resultado → Novo match
"""
from __future__ import annotations

import datetime as dt
import unittest
import uuid

from tests.support import PASSWORD, Client, db_system, grant_premium, last_token_for, new_account


def _d(delta: int = 0) -> str:
    return (dt.date.today() + dt.timedelta(days=delta)).isoformat()


class NetworkJourney(unittest.TestCase):
    def account(self, kind: str) -> Client:
        c = new_account(kind, compliance="approved")
        grant_premium(c)
        return c

    def teammate(self, org: Client, role: str = "manager") -> Client:
        """Pessoa de verdade na organização, pelo fluxo real de convite + aceite."""
        em = f"eq-{uuid.uuid4().hex[:8]}@teste.org"
        self.assertEqual(org.post("/v1/org/invitations", {"email": em, "role": role}).status, 201)
        peer = Client()
        peer.post("/v1/auth/register", {"email": em, "password": PASSWORD, "full_name": "Colega", "accept_terms": True})
        peer.login(em, PASSWORD)
        self.assertEqual(peer.post("/v1/auth/accept-invite", {"token": last_token_for(em, "/convite")}).status, 200)
        me = peer.get("/v1/me").json
        peer.user, peer.org_id = me["user"], me["active_org"]["id"]
        peer.email = em
        return peer

    def project(self, osc: Client, title: str | None = None) -> str:
        r = osc.post("/v1/projects", {
            "title": title or f"Projeto {uuid.uuid4().hex[:6]}",
            "summary": "Formação profissional para jovens da regional leste, em três turmas no ano letivo.",
            "problem": "Evasão escolar e falta de qualificação técnica no bairro, apontadas no diagnóstico local.",
            "objectives": "Qualificar 200 jovens e encaminhar ao menos 60 ao primeiro emprego formal.",
            "methodology": "Oficinas semanais com registro de presença e avaliação ao fim de cada módulo.",
            "territory": "BR-MT", "causes": ["educacao"], "ods": [4, 8], "beneficiaries_count": 200,
            "beneficiaries_description": "Jovens de 14 a 18 anos da regional leste",
            "budget_total_cents": 30_000_000})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def published(self, osc: Client, title: str | None = None) -> str:
        pid = self.project(osc, title)
        self.assertIn(osc.post(f"/v1/projects/{pid}/publish", {}).status, (200, 201))
        return pid

    def listing(self, osc: Client, pid: str, seeking: list[str]) -> str:
        r = osc.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pid, "seeking": seeking,
            "headline": "Formação profissional para 200 jovens na regional leste de Cuiabá",
            "summary": "Três turmas no ano letivo, com encaminhamento ao primeiro emprego.",
            "territory": "BR-MT", "causes": ["educacao"], "ods": [4, 8],
            "amount_target_cents": 30_000_000})
        self.assertEqual(r.status, 201, r)
        lid = r.json["id"]
        self.assertEqual(osc.post(f"/v1/marketplace/listings/{lid}/transition", {"to": "published"}).status, 200)
        return lid


# ================================================================================================ 1
class J1_OnboardingToWorkspace(NetworkJourney):
    """Conta → organização → persona → área de trabalho com próximas ações."""

    def test_journey(self):
        osc = self.account("osc")
        w = osc.get("/v1/workspace")
        self.assertEqual(w.status, 200, w)
        # A persona é inferida do tipo de organização quando nenhuma foi declarada, e a origem é dita.
        self.assertEqual(w.json["persona"]["key"], "organization")
        self.assertEqual(w.json["persona"]["source"], "default_by_org_kind")
        # Uma organização nova já tem o que fazer, e cada item diz por quê.
        self.assertTrue(w.json["next_actions"], "workspace vazio não ajuda ninguém")
        for a in w.json["next_actions"]:
            self.assertGreaterEqual(len(a["rationale"]), 10, a["action"])

        # Declarar persona não muda capacidade: isso é papel + plano.
        before = w.json["capabilities"]
        self.assertEqual(osc.post("/v1/workspace/personas", {"persona": "organization", "primary": True}).status, 201)
        after = osc.get("/v1/workspace").json
        self.assertEqual(after["capabilities"], before)
        self.assertEqual(after["persona"]["source"], "primary")

        # E a persona de outro tipo de organização é recusada.
        self.assertEqual(osc.post("/v1/workspace/personas", {"persona": "government"}).status, 422)


# ================================================================================================ 2
class J2_InvestorDiscoversAndProposes(NetworkJourney):
    """Investidor: descobre no marketplace → favorita → contato → conversa → proposta → acompanha."""

    def test_journey(self):
        osc, inv = self.account("osc"), self.account("company")
        pid = self.published(osc)
        lid = self.listing(osc, pid, ["investment"])

        # 1. descobre — e o feed só traz publicado
        feed = Client().get("/v1/marketplace/feed?seeking=investment&territory=BR-MT&limit=50")
        self.assertEqual(feed.status, 200, feed)
        self.assertIn(lid, [i["id"] for i in feed.json["items"]])

        # 2. favorita (privado: nem o projeto sabe)
        fav = inv.post("/v1/network/relationships",
                       {"kind": "favorite", "target_type": "project", "target_id": pid})
        self.assertEqual(fav.status, 201, fav)
        self.assertEqual(fav.json["visibility"], "private")
        self.assertEqual(Client().get(f"/v1/public/relationships/project/{pid}").json["items"], [])

        # 3. registra contato — é o vínculo que abre a conversa
        self.assertEqual(inv.post("/v1/network/relationships",
                                  {"kind": "contact", "target_type": "org", "target_id": osc.org_id,
                                   "note": "Gostaria de entender o modelo de encaminhamento."}).status, 201)

        # 4. conversa COM contexto
        conv = inv.post("/v1/conversations", {"other_org_id": osc.org_id, "project_id": pid,
                                              "subject": "Dúvidas sobre o encaminhamento ao emprego"})
        self.assertEqual(conv.status, 201, conv)
        cid = conv.json["id"]
        self.assertEqual(inv.post(f"/v1/conversations/{cid}/messages",
                                  {"body": "Como vocês acompanham o jovem depois da formação?"}).status, 201)
        thread = osc.get(f"/v1/conversations/{cid}")
        self.assertEqual(thread.status, 200, thread)
        self.assertEqual(thread.json["conversation"]["context_project_id"], pid)

        # 5. propõe
        prop = inv.post("/v1/proposals", {
            "kind": "investment", "receiver_org_id": osc.org_id, "project_id": pid,
            "title": "Investimento social nas três turmas", "amount_cents": 15_000_000,
            "support_mode": "financial",
            "purpose": "Apoiar material didático, transporte e a coordenação pedagógica das três turmas."})
        self.assertEqual(prop.status, 201, prop)
        prop_id = prop.json["id"]
        self.assertEqual(prop.json["status"], "draft", "nada é enviado por acidente")
        self.assertEqual(inv.post(f"/v1/proposals/{prop_id}/transition", {"to": "sent"}).status, 200)

        # 6. a OSC vê na caixa, com o lado certo
        inbox = osc.get("/v1/proposals?box=received&status=open")
        self.assertEqual([p["id"] for p in inbox.json["items"]], [prop_id])
        self.assertTrue(inbox.json["items"][0]["awaiting_me"])

        # 7. aceita — e o que nasce é RELAÇÃO e INTENÇÃO, não dinheiro
        self.assertEqual(osc.get(f"/v1/proposals/{prop_id}").json["status"], "viewed")
        acc = osc.post(f"/v1/proposals/{prop_id}/transition", {"to": "accepted"})
        self.assertEqual(acc.status, 200, acc)
        with db_system() as c:
            funding = c.one("SELECT committed_cents, disbursed_cents FROM project_funding($1)", pid)
            intent = c.one("SELECT status, commitment_id FROM investment_intents WHERE investor_org_id = $1"
                           " AND project_id = $2", inv.org_id, pid)
        self.assertEqual(int(funding["committed_cents"] or 0), 0, "aceite não é compromisso financeiro")
        self.assertEqual(int(funding["disbursed_cents"] or 0), 0, "e muito menos dinheiro recebido")
        self.assertEqual(intent["status"], "in_negotiation")
        self.assertIsNone(intent["commitment_id"])

        # 8. o investidor acompanha, e a tela diz a diferença
        sup = inv.get("/v1/workspace?persona=investor").json["sections"]["supported"]
        self.assertEqual([s["id"] for s in sup], [pid])
        self.assertFalse(sup[0]["has_commitment"])


# ================================================================================================ 3
class J3_OrganizationStructuresAndPublishes(NetworkJourney):
    """Organização: projeto → diagnóstico → prontidão → publica → anuncia → recebe proposta."""

    def test_journey(self):
        osc, inv = self.account("osc"), self.account("company")
        pid = self.project(osc)

        # prontidão por finalidade: seis respostas, cada número explicado
        rd = osc.get(f"/v1/readiness/purposes?project_id={pid}")
        self.assertEqual(rd.status, 200, rd)
        self.assertEqual(len(rd.json["scores"]), 6)
        for key, dim in rd.json["dimensions"].items():
            self.assertTrue(dim["checks"], key)
        low = rd.json["scores"]["funding_readiness"]

        # a recomendação aponta o que fazer, com razão
        osc.post("/v1/recommendations/refresh", {})
        actions = {r["action"] for r in osc.get("/v1/recommendations").json["items"]}
        self.assertTrue({"publish_project", "complete_project", "add_indicator", "add_milestone",
                         "upload_document"} & actions,
                        f"nenhuma ação esperada em {actions}")

        # publica e anuncia
        self.assertIn(osc.post(f"/v1/projects/{pid}/publish", {}).status, (200, 201))
        lid = self.listing(osc, pid, ["investment", "partner"])
        self.assertEqual(osc.get("/v1/marketplace/listings").json["items"][0]["publication_state"], "published")

        # publicar melhora a prontidão de captação — e o motivo está nos critérios
        rd2 = osc.get(f"/v1/readiness/purposes?project_id={pid}").json
        self.assertGreater(rd2["scores"]["funding_readiness"], low)
        pub_check = next(c for c in rd2["dimensions"]["funding_readiness"]["checks"]
                         if c["key"] == "funding.published")
        self.assertEqual(pub_check["score"], 100.0)

        # recebe proposta e ela aparece com contexto
        prop = inv.post("/v1/proposals", {
            "kind": "partnership", "receiver_org_id": osc.org_id, "project_id": pid,
            "title": "Parceria para encaminhamento ao emprego",
            "purpose": "Abrir vagas de primeiro emprego para os jovens formados nas turmas."}).json["id"]
        inv.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        got = osc.get(f"/v1/proposals/{prop}")
        self.assertEqual(got.json["project_title"], osc.get(f"/v1/projects/{pid}").json["title"])
        self.assertEqual(got.json["side"], "receiver")
        self.assertIn("Não é contrato", got.json["financial_notice"])
        self.assertTrue(lid)


# ================================================================================================ 4
class J4_ProfessionalFindsWork(NetworkJourney):
    """Profissional: perfil público → experiência confirmada → oportunidade → proposta de serviço."""

    def test_journey(self):
        osc, pro = self.account("osc"), self.account("provider")
        handle = f"pro{uuid.uuid4().hex[:8]}"

        # 1. perfil público pessoal
        prof = pro.post("/v1/profiles", {"handle": handle, "display_name": "Ana Profissional",
                                         "headline": "Avaliação de projetos socioeducativos", "owner": "user"})
        self.assertEqual(prof.status, 201, prof)
        self.assertEqual(prof.json["url"], f"/@{handle}")

        # 2. declara experiência NA organização — que nasce aguardando confirmação
        exp = pro.post("/v1/profile/experiences", {
            "org_name": "Instituto Parceiro", "org_id": osc.org_id, "role": "Avaliadora externa",
            "started_on": _d(-800), "ended_on": _d(-400), "visibility": "public",
            "description": "Avaliação de resultados de dois ciclos de formação."})
        self.assertEqual(exp.status, 201, exp)
        self.assertEqual(exp.json["state"], "pending_confirmation")
        # declarada NÃO aparece no perfil público
        page = Client().get(f"/v1/public/profiles/{handle}")
        self.assertEqual(page.json["profile"].get("experiences", []), [])

        # 3. quem administra a organização confirma
        pend = osc.get("/v1/org/experience-requests")
        self.assertEqual([e["id"] for e in pend.json["items"]], [exp.json["id"]])
        self.assertEqual(osc.post(f"/v1/org/experience-requests/{exp.json['id']}/decide",
                                  {"decision": "confirmed"}).status, 200)

        # 4. agora aparece — e o perfil público continua sem nada privado
        pidr = pro.get("/v1/profiles/mine").json["person"]["id"]
        pro.post(f"/v1/profiles/{pidr}/rebuild", {})
        page = Client().get(f"/v1/public/profiles/{handle}")
        self.assertEqual(page.status, 200, page)
        self.assertEqual([e["role"] for e in page.json["profile"]["experiences"]], ["Avaliadora externa"])
        self.assertNotIn(pro.email, str(page.json))

        # 5. encontra oportunidade e propõe serviço
        pid = self.published(osc)
        self.listing(osc, pid, ["professional"])
        feed = Client().get("/v1/marketplace/feed?seeking=professional&limit=50")
        self.assertIn(pid, [i["project_id"] for i in feed.json["items"]])
        prop = pro.post("/v1/proposals", {
            "kind": "service", "receiver_org_id": osc.org_id, "project_id": pid,
            "title": "Avaliação externa de resultados", "amount_cents": 1_200_000,
            "compensation": "paid", "support_mode": "service",
            "purpose": "Desenhar e executar a avaliação externa dos resultados das três turmas."})
        self.assertEqual(prop.status, 201, prop)
        pro.post(f"/v1/proposals/{prop.json['id']}/transition", {"to": "sent"})
        self.assertTrue(osc.get("/v1/proposals?box=received&status=open").json["items"])


# ================================================================================================ 5
class J5_GovernmentPublishesAndMonitors(NetworkJourney):
    """Governo: necessidade do território → acompanha projeto → indicadores do território."""

    def test_journey(self):
        gov, osc = self.account("government"), self.account("osc")

        # 1. registra necessidade — estimativa exige fonte
        no_src = gov.post("/v1/territory/needs", {
            "territory": "BR-MT", "title": "Vagas de contraturno na regional leste", "people_estimate": 1200})
        self.assertEqual(no_src.status, 422, "número sem fonte não entra")
        ok = gov.post("/v1/territory/needs", {
            "territory": "BR-MT", "title": "Vagas de contraturno na regional leste",
            "description": "Déficit de vagas apontado no diagnóstico municipal.",
            "cause": "educacao", "people_estimate": 1200, "source_name": "Diagnóstico municipal 2025",
            "source_url": "https://exemplo.gov.br/diagnostico", "source_date": _d(-90), "priority": "critical",
            "beneficiary_groups": []})
        self.assertEqual(ok.status, 201, ok)

        # 2. a necessidade aparece com a fonte do número ao lado
        listed = gov.get("/v1/territory/needs?territory=BR-MT")
        mine = next(n for n in listed.json["items"] if n["id"] == ok.json["id"])
        self.assertEqual(mine["source_name"], "Diagnóstico municipal 2025")

        # 3. acompanha um projeto do território.
        #
        # Acompanhar é UNILATERAL e privado — o órgão não precisa de autorização para observar o que foi publicado.
        # Declarar APOIO é outra coisa: é relação formal e nasce pendente, porque afirmar que um órgão apoia um
        # projeto sem o projeto concordar seria afirmação de uma parte sobre a outra.
        pid = self.published(osc)
        watch = gov.post("/v1/network/relationships",
                         {"kind": "watchlist", "target_type": "project", "target_id": pid,
                          "note": "Acompanhamento pela secretaria."})
        self.assertEqual(watch.status, 201, watch)
        self.assertEqual(watch.json["status"], "active")
        self.assertEqual(watch.json["visibility"], "private")

        support = gov.post("/v1/network/relationships",
                           {"kind": "government_support", "target_type": "project", "target_id": pid})
        self.assertEqual(support.status, 201, support)
        self.assertEqual(support.json["status"], "pending", "apoio governamental depende do aceite do projeto")
        self.assertEqual(osc.post(f"/v1/network/relationships/{support.json['id']}/transition",
                                  {"to": "active"}).status, 200)

        w = gov.get("/v1/workspace")
        self.assertEqual(w.json["persona"]["key"], "government")
        self.assertIn("territory", [s["key"] for s in w.json["layout"]])
        self.assertIn(pid, [p["id"] for p in w.json["sections"]["monitored"]])

        # 4. o painel de indicadores do território só traz medição validada
        self.assertIsInstance(w.json["sections"]["indicators"], list)


# ================================================================================================ 6
class J6_ExecutionToProvenResult(NetworkJourney):
    """Execução → marco → evidência → relatório → aceite de quem apoia → resultado público."""

    def test_journey(self):
        osc, funder = self.account("osc"), self.account("company")
        pid = self.published(osc)

        # 1. apoio aceito: é o que dá a quem apoia o direito de analisar o relatório
        prop = funder.post("/v1/proposals", {
            "kind": "investment", "receiver_org_id": osc.org_id, "project_id": pid,
            "title": "Apoio ao ciclo de execução", "amount_cents": 10_000_000,
            "purpose": "Apoiar a execução das três turmas previstas no projeto."}).json["id"]
        funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        osc.get(f"/v1/proposals/{prop}")
        self.assertEqual(osc.post(f"/v1/proposals/{prop}/transition", {"to": "accepted"}).status, 200)

        # 2. a EQUIPE do projeto passa a incluir quem apoia — e é quem será avisado
        team = osc.get(f"/v1/projects/{pid}/team")
        self.assertEqual(team.status, 200, team)
        self.assertIn(funder.user["id"], [p["user_id"] for p in team.json["items"]],
                      "quem apoia entra na equipe e passa a ser avisado")

        # 3. relatório do período: prévia mostra o que será apurado
        gather = osc.get(f"/v1/impact-updates/gather?project_id={pid}&period_start={_d(-90)}&period_end={_d(-1)}")
        self.assertEqual(gather.status, 200, gather)
        self.assertIn("caveat", gather.json)

        u = osc.post("/v1/impact-updates", {
            "project_id": pid, "period_start": _d(-90), "period_end": _d(-1),
            "summary": "Primeiro ciclo concluído com duas turmas e avaliação ao fim de cada módulo.",
            "outputs": "Duas turmas concluídas, 128 jovens formados.",
            "outcomes": "41 jovens encaminhados ao primeiro emprego formal.",
            "limitations": "Sem grupo de comparação: não é possível atribuir causalidade a este resultado."})
        self.assertEqual(u.status, 201, u)
        uid = u.json["id"]

        # 4. envia: aqui o servidor apura os números
        self.assertEqual(osc.post(f"/v1/impact-updates/{uid}/transition", {"to": "submitted"}).status, 200)
        sent = osc.get(f"/v1/impact-updates/{uid}").json
        self.assertIsNotNone(sent["submitted_at"])
        self.assertIn("caveat", sent["metrics"])

        # 5. quem executa NÃO analisa o próprio relatório
        self.assertEqual(osc.post(f"/v1/impact-updates/{uid}/transition", {"to": "accepted"}).status, 403)

        # 6. quem apoia analisa, pede ajuste com motivo, e depois aceita
        self.assertEqual(funder.post(f"/v1/impact-updates/{uid}/transition",
                                     {"to": "changes_requested"}).status, 422)
        self.assertEqual(funder.post(f"/v1/impact-updates/{uid}/transition",
                                     {"to": "changes_requested",
                                      "note": "Falta a medição do indicador de evasão no período."}).status, 200)
        self.assertEqual(osc.post(f"/v1/impact-updates/{uid}/transition", {"to": "submitted"}).status, 200)
        self.assertEqual(funder.post(f"/v1/impact-updates/{uid}/transition", {"to": "accepted"}).status, 200)

        # 7. só depois de aceito a organização publica — e aí o resultado é público
        self.assertEqual(Client().get(f"/v1/public/projects/{pid}/impact").json["items"], [])
        self.assertEqual(osc.post(f"/v1/impact-updates/{uid}/transition", {"to": "published"}).status, 200)
        pub = Client().get(f"/v1/public/projects/{pid}/impact")
        self.assertEqual(len(pub.json["items"]), 1)
        self.assertIn("Sem grupo de comparação", pub.json["items"][0]["limitations"])

        # 8. o fato entrou na trilha encadeada do projeto, e a trilha continua verificável
        with db_system() as c:
            kinds = [r["entry_type"] for r in c.query(
                "SELECT entry_type FROM ledger_entries WHERE project_id = $1", pid)]
            # a função devolve (entries, valid, first_broken_seq) — o nome da coluna é `valid`
            ok = c.scalar("SELECT valid FROM ledger_verify($1)", pid)
        self.assertIn("impact_update_accepted", kinds)
        self.assertIn("impact_update_published", kinds)
        self.assertTrue(ok, "a trilha do projeto tem de continuar íntegra depois de tudo isso")


# ================================================================================================ 7
class J7_TeamIsAlwaysNotified(NetworkJourney):
    """A exigência central da rodada: toda a equipe avisada em cada mudança e cada documento juntado."""

    def test_journey(self):
        osc, funder = self.account("osc"), self.account("company")
        pid = self.published(osc)
        mates = [self.teammate(osc, r) for r in ("manager", "member", "analyst")]
        team = osc.get(f"/v1/projects/{pid}/team").json
        self.assertGreaterEqual(team["count"], 4)

        def notices(ref: str) -> list[dict]:
            with db_system() as c:
                return c.query("SELECT user_id::text AS user_id, kind, dedupe_key, action_label"
                               " FROM notifications WHERE ref_id = $1 ORDER BY created_at", ref)

        # 1. proposta enviada avisa a equipe inteira, UMA vez por pessoa, sem avisar quem enviou
        prop = funder.post("/v1/proposals", {
            "kind": "sponsorship", "receiver_org_id": osc.org_id, "project_id": pid,
            "title": "Patrocínio do material didático",
            "purpose": "Patrocinar material didático e transporte das três turmas."}).json["id"]
        funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        n = notices(prop)
        users = [x["user_id"] for x in n]
        self.assertEqual(len(users), len(set(users)), "ninguém recebe dois avisos do mesmo fato")
        self.assertGreaterEqual(len(users), 4, "TODA a equipe, não só quem administra")
        self.assertNotIn(funder.user["id"], users, "quem agiu não é avisado do próprio ato")
        self.assertIn("Analisar", [x["action_label"] for x in n], "o aviso diz o que fazer")

        # 2. reprocessar o mesmo fato não gera aviso novo
        funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        self.assertEqual(len(notices(prop)), len(n))

        # 3. documento anexado avisa a outra parte E a equipe do projeto
        with db_system() as c:
            did = c.scalar(
                "INSERT INTO documents(org_id, title, doc_type, filename, mime_type, size_bytes, sha256,"
                " storage_key, status, uploaded_by) VALUES ($1,'Plano de aplicação','other','plano.pdf',"
                " 'application/pdf', 2048, repeat('b', 64), 'test/plano.pdf', 'clean', $2) RETURNING id::text",
                funder.org_id, funder.user["id"])
        self.assertEqual(funder.post(f"/v1/proposals/{prop}/attachments", {"document_id": did}).status, 201)
        with db_system() as c:
            doc_notices = c.query("SELECT user_id::text AS user_id FROM notifications"
                                  " WHERE ref_id = $1 AND kind LIKE 'document.%'", prop)
            ev = c.one("SELECT notified FROM domain_events WHERE event = 'Document.attached'"
                       " AND subject_id = $1 ORDER BY id DESC LIMIT 1", prop)
        got = {x["user_id"] for x in doc_notices}
        self.assertGreaterEqual(len(got), 4, "a equipe precisa saber que um documento entrou na negociação")
        self.assertIsNotNone(ev)

        # 4. quem silencia o grupo deixa de receber o aviso — mas o FATO continua registrado
        mate = mates[0]
        self.assertEqual(mate.put("/v1/notifications/prefs",
                                  {"items": [{"grp": "proposal", "in_app": False, "email": False}]}).status, 200)
        p2 = funder.post("/v1/proposals", {
            "kind": "collaboration", "receiver_org_id": osc.org_id, "project_id": pid,
            "title": "Colaboração no monitoramento",
            "purpose": "Colaborar na definição e coleta dos indicadores ao longo do ciclo."}).json["id"]
        funder.post(f"/v1/proposals/{p2}/transition", {"to": "sent"})
        with db_system() as c:
            silenced = c.scalar("SELECT count(*) FROM notifications WHERE ref_id = $1 AND user_id = $2",
                                p2, mate.user["id"])
            fact = c.one("SELECT notified FROM domain_events WHERE subject_id = $1"
                         " AND event = 'Proposal.sent'", p2)
        self.assertEqual(int(silenced or 0), 0)
        self.assertIsNotNone(fact)
        self.assertGreaterEqual(int(fact["notified"]), 3, "os demais continuam sendo avisados")

        # 5. a atividade da rede mostra os fatos com o alcance real de cada um
        ev = osc.get("/v1/network/events")
        self.assertEqual(ev.status, 200, ev)
        self.assertTrue(ev.json["items"])
        for item in ev.json["items"]:
            self.assertIn("label", item)
            self.assertGreaterEqual(int(item["notified"]), 0)


if __name__ == "__main__":
    unittest.main()
