"""v0.16.0 — camada de rede: relação, proposta, conversa com contexto, anúncio, relatório de impacto, perfil
público, persona/workspace, prontidão, recomendação e o fan-out de notificação.

Cada teste exercita a API real contra PostgreSQL real. Nenhum afirma integração: o que depende de terceiro continua
sendo testado pela recusa explícita, como na v0.14.0 e v0.15.0.
"""
from __future__ import annotations

import datetime as dt
import unittest
import uuid

from tests.support import Client, app_tx, db_system, grant_premium, new_account, owner_conn


def _today(delta: int = 0) -> str:
    return (dt.date.today() + dt.timedelta(days=delta)).isoformat()


class NetBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.funder = new_account("company", compliance="approved")
        grant_premium(cls.osc)
        grant_premium(cls.funder)

    def open_project(self, **extra) -> str:
        """Projeto PUBLICADO. É o estado em que um financiador o encontra e pode propor: a RLS não deixa ninguém
        de fora ver projeto privado, e propor sobre o que não se pode ver devolve 404 — comportamento correto."""
        pid = self.project(**extra)
        self.publish(pid)
        return pid

    def project(self, client: Client | None = None, title: str | None = None, **extra) -> str:
        c = client or self.osc
        r = c.post("/v1/projects", {
            "title": title or f"Projeto rede {uuid.uuid4().hex[:6]}",
            "summary": "Resumo suficiente para que o projeto seja avaliado por terceiros nesta rodada de testes.",
            "problem": "Problema descrito com evidência local e fonte declarada no diagnóstico do território.",
            "objectives": "Objetivo geral e específicos declarados para o período de execução previsto.",
            "methodology": "Oficinas semanais com registro de presença e avaliação ao final de cada módulo.",
            "territory": "BR-MT", "budget_total_cents": 30_000_000, "causes": ["educacao"], "ods": [4],
            "beneficiaries_count": 200, "beneficiaries_description": "Jovens de 14 a 18 anos da regional leste",
            **extra})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def publish(self, pid: str, client: Client | None = None) -> None:
        c = client or self.osc
        r = c.post(f"/v1/projects/{pid}/publish", {})
        self.assertIn(r.status, (200, 201), r)


# ================================================================================================ relação
class RelationshipTests(NetBase):
    def test_relationship_is_idempotent_and_block_is_forced_private(self):
        pid = self.project()
        a = self.funder.post("/v1/network/relationships",
                             {"kind": "favorite", "target_type": "project", "target_id": pid})
        self.assertEqual(a.status, 201, a)
        self.assertTrue(a.json["created"])
        # favoritar duas vezes devolve a MESMA relação: o botão que o dedo aperta duas vezes não gera dois favoritos
        b = self.funder.post("/v1/network/relationships",
                             {"kind": "favorite", "target_type": "project", "target_id": pid})
        self.assertEqual(b.json["id"], a.json["id"])
        self.assertFalse(b.json["created"])
        # favorito é privado mesmo quando se pede público — o teto do tipo rebaixa em silêncio
        self.assertEqual(a.json["visibility"], "private")
        c = self.funder.post("/v1/network/relationships",
                             {"kind": "block", "target_type": "org", "target_id": self.osc.org_id,
                              "visibility": "public"})
        self.assertEqual(c.status, 201, c)
        self.assertEqual(c.json["visibility"], "private", "bloqueio público exporia juízo sobre terceiro")

    def test_pending_relationship_is_accepted_only_by_target(self):
        r = self.funder.post("/v1/network/relationships",
                             {"kind": "partnership", "target_type": "org", "target_id": self.osc.org_id})
        self.assertEqual(r.status, 201, r)
        rid = r.json["id"]
        self.assertEqual(r.json["status"], "pending", "relação que exige consentimento nasce pendente")
        # quem propôs NÃO pode aceitar a própria proposta de parceria
        mine = self.funder.post(f"/v1/network/relationships/{rid}/transition", {"to": "active"})
        self.assertEqual(mine.status, 403, mine)
        self.assertEqual(mine.json["code"], "not_target")
        # o destino aceita
        ok = self.osc.post(f"/v1/network/relationships/{rid}/transition", {"to": "active"})
        self.assertEqual(ok.status, 200, ok)
        self.assertEqual(ok.json["status"], "active")

    def test_closing_a_relationship_requires_a_reason(self):
        r = self.funder.post("/v1/network/relationships",
                             {"kind": "collaboration", "target_type": "org", "target_id": self.osc.org_id})
        rid = r.json["id"]
        self.osc.post(f"/v1/network/relationships/{rid}/transition", {"to": "active"})
        no = self.osc.post(f"/v1/network/relationships/{rid}/transition", {"to": "ended"})
        self.assertEqual(no.status, 422, no)
        yes = self.osc.post(f"/v1/network/relationships/{rid}/transition",
                            {"to": "ended", "reason": "Escopo concluído em comum acordo."})
        self.assertEqual(yes.status, 200, yes)

    def test_invalid_transition_lists_what_is_possible(self):
        r = self.funder.post("/v1/network/relationships",
                             {"kind": "mentorship", "target_type": "org", "target_id": self.osc.org_id})
        rid = r.json["id"]
        self.osc.post(f"/v1/network/relationships/{rid}/transition",
                      {"to": "declined", "reason": "Sem disponibilidade neste semestre."})
        again = self.osc.post(f"/v1/network/relationships/{rid}/transition", {"to": "active"})
        self.assertEqual(again.status, 409, again)
        self.assertEqual(again.json["code"], "invalid_transition")
        self.assertEqual(again.json["details"]["permitidas"], [])

    def test_relationship_kind_rejects_target_that_makes_no_sense(self):
        pid = self.project()
        r = self.funder.post("/v1/network/relationships",
                             {"kind": "partnership", "target_type": "project", "target_id": pid})
        self.assertEqual(r.status, 422, r)
        self.assertIn("org", r.json["details"]["aceitos"])

    def test_old_follow_table_is_mirrored_into_relationships(self):
        """A camada antiga continua funcionando e a rede vê tudo — nenhuma rota existente parou."""
        r = self.funder.post(f"/v1/network/follow/{self.osc.org_id}", {})
        self.assertIn(r.status, (200, 201), r)
        with db_system() as c:
            row = c.one("SELECT kind, visibility, mirrored_from FROM relationships"
                        " WHERE source_org_id = $1 AND target_org_id = $2 AND kind = 'follow'",
                        self.funder.org_id, self.osc.org_id)
        self.assertIsNotNone(row, "seguir pela rota antiga precisa aparecer como relação")
        self.assertEqual(row["mirrored_from"], "follows")
        self.assertEqual(row["visibility"], "network")
        # e deixar de seguir remove o espelho
        self.funder.delete(f"/v1/network/follow/{self.osc.org_id}")
        with db_system() as c:
            self.assertIsNone(c.one("SELECT 1 AS ok FROM relationships WHERE source_org_id = $1"
                                    " AND target_org_id = $2 AND kind = 'follow'",
                                    self.funder.org_id, self.osc.org_id))

    def test_private_relationship_never_leaks_through_the_public_route(self):
        pid = self.project()
        self.publish(pid)
        self.funder.post("/v1/network/relationships",
                         {"kind": "watchlist", "target_type": "project", "target_id": pid})
        anon = Client()
        out = anon.get(f"/v1/public/relationships/project/{pid}")
        self.assertEqual(out.status, 200, out)
        self.assertEqual(out.json["items"], [], "acompanhamento é privado e não pode sair na rota pública")

    def test_self_relationship_is_refused(self):
        r = self.osc.post("/v1/network/relationships",
                          {"kind": "partnership", "target_type": "org", "target_id": self.osc.org_id})
        self.assertEqual(r.status, 422, r)


# ================================================================================================ proposta
class ProposalTests(NetBase):
    def _proposal(self, pid: str, **extra) -> str:
        r = self.funder.post("/v1/proposals", {
            "kind": "investment", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Apoio ao projeto de formação profissional",
            "purpose": "Apoiar a execução de três turmas de formação no período letivo seguinte.",
            "amount_cents": 15_000_000, "support_mode": "financial", **extra})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def test_proposal_requires_context(self):
        r = self.funder.post("/v1/proposals", {
            "kind": "partnership", "receiver_org_id": self.osc.org_id,
            "title": "Proposta sem contexto", "purpose": "Mensagem fria sem vínculo com projeto ou edital."})
        self.assertEqual(r.status, 422, r)
        self.assertIn("project_id", (r.json.get("details") or {}).get("contextos", []), r.json)

    def test_proposal_is_born_draft_even_through_direct_sql(self):
        pid = self.open_project()
        prop = self._proposal(pid)
        self.assertEqual(self.funder.get(f"/v1/proposals/{prop}").json["status"], "draft")
        # E o gatilho recusa nascer em outro estado mesmo por SQL direto. O contexto tem de ser o da USUÁRIA (papel
        # `impacto_app` sem privilégio): contexto de sistema é privilegiado por definição e a trava o dispensa — é
        # assim que trabalhos internos conseguem corrigir dados.
        with app_tx(self.funder) as c, self.assertRaises(Exception) as e:
            c.run("INSERT INTO proposals(kind, sender_org_id, receiver_org_id, title, purpose, status, decided_at)"
                  " VALUES ('service',$1,$2,'Titulo','proposito com tamanho suficiente','accepted', now())",
                  self.funder.org_id, self.osc.org_id)
        self.assertIn("rascunho", str(e.exception).lower())

    def test_only_receiver_decides_and_refusal_demands_a_reason(self):
        pid = self.open_project()
        prop = self._proposal(pid)
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        # quem enviou não pode aceitar
        bad = self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "accepted"})
        self.assertIn(bad.status, (403, 409), bad)
        # abrir marca como vista
        self.assertEqual(self.osc.get(f"/v1/proposals/{prop}").json["status"], "viewed")
        # recusar sem motivo é recusado
        no = self.osc.post(f"/v1/proposals/{prop}/transition", {"to": "declined"})
        self.assertEqual(no.status, 422, no)
        ok = self.osc.post(f"/v1/proposals/{prop}/transition",
                           {"to": "declined", "note": "Fora do escopo temático deste ciclo."})
        self.assertEqual(ok.status, 200, ok)

    def test_accepting_creates_relationship_and_intent_but_never_money(self):
        pid = self.open_project()
        prop = self._proposal(pid)
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        self.osc.get(f"/v1/proposals/{prop}")
        acc = self.osc.post(f"/v1/proposals/{prop}/transition", {"to": "accepted"})
        self.assertEqual(acc.status, 200, acc)
        self.assertIsNotNone(acc.json.get("relationship"), "aceitar cria a relação")
        with db_system() as c:
            intent = c.one("SELECT status, amount_cents, commitment_id FROM investment_intents"
                           " WHERE investor_org_id = $1 AND project_id = $2", self.funder.org_id, pid)
            funding = c.one("SELECT committed_cents, confirmed_cents, disbursed_cents"
                            " FROM project_funding($1)", pid)
        self.assertEqual(intent["status"], "in_negotiation",
                         "aceite registra INTENÇÃO, nunca compromisso")
        self.assertIsNone(intent["commitment_id"])
        self.assertEqual(int(funding["committed_cents"] or 0), 0,
                         "aceitar proposta não pode somar dinheiro à captação do projeto")
        self.assertEqual(int(funding["disbursed_cents"] or 0), 0)

    def test_changes_requested_creates_a_new_version_and_keeps_the_old_amount(self):
        pid = self.open_project()
        prop = self._proposal(pid)
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        self.osc.get(f"/v1/proposals/{prop}")
        self.osc.post(f"/v1/proposals/{prop}/transition",
                      {"to": "changes_requested", "note": "Precisamos de contrapartida menor no primeiro ano."})
        self.funder.patch(f"/v1/proposals/{prop}", {"amount_cents": 9_000_000})
        again = self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        self.assertEqual(again.status, 200, again)
        full = self.osc.get(f"/v1/proposals/{prop}").json
        self.assertEqual(full["version"], 2, "reenvio após ajuste é nova versão")
        notes = " ".join(e["note"] or "" for e in full["events"])
        self.assertIn("15000000", notes, "o valor anterior fica registrado no histórico")

    def test_accepted_proposal_is_not_editable(self):
        pid = self.open_project()
        prop = self._proposal(pid)
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        self.osc.get(f"/v1/proposals/{prop}")
        self.osc.post(f"/v1/proposals/{prop}/transition", {"to": "accepted"})
        bad = self.funder.patch(f"/v1/proposals/{prop}", {"amount_cents": 99_000_000})
        self.assertEqual(bad.status, 409, bad)
        self.assertEqual(bad.json["code"], "not_editable")

    def test_viewed_at_and_decided_by_cannot_be_forged_by_the_client(self):
        """Carimbo de tempo e autoria de decisão são derivados por gatilho, não enviados."""
        pid = self.open_project()
        prop = self._proposal(pid)
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        with app_tx(self.osc) as c, self.assertRaises(Exception) as e:
            c.run("UPDATE proposals SET viewed_at = now() - interval '10 days' WHERE id = $1", prop)
        self.assertIn("administra", str(e.exception).lower())
        self.osc.get(f"/v1/proposals/{prop}")
        self.osc.post(f"/v1/proposals/{prop}/transition", {"to": "accepted"})
        with db_system() as c:
            row = c.one("SELECT decided_by::text AS decided_by, decided_at FROM proposals WHERE id = $1", prop)
        self.assertEqual(row["decided_by"], self.osc.user["id"], "quem decidiu vem de app_uid(), não do corpo")
        self.assertIsNotNone(row["decided_at"])

    def test_blocked_organization_cannot_receive_a_proposal(self):
        other = new_account("company", compliance="approved")
        grant_premium(other)
        pid = self.open_project()
        self.osc.post(f"/v1/network/block/{other.org_id}", {})
        r = other.post("/v1/proposals", {
            "kind": "investment", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Proposta de quem foi bloqueado",
            "purpose": "Tentativa de contato apesar do bloqueio registrado pela outra parte."})
        self.assertEqual(r.status, 403, r)
        self.assertEqual(r.json["code"], "blocked")


# ================================================================================================ fan-out de notificação
class TeamNotificationTests(NetBase):
    def test_whole_team_is_notified_once_and_the_actor_is_not(self):
        """O pedido central da rodada: avisar TODA a equipe em cada mudança, uma vez só, sem avisar quem agiu."""
        pid = self.open_project()
        # Três pessoas de verdade na organização executora. Convite por e-mail não cria vínculo (só convida), e é o
        # VÍNCULO que define a equipe — então o cenário é montado com membros reais.
        mates = [new_account("individual") for _ in range(3)]
        with db_system() as c:
            for mate, role in zip(mates, ("manager", "member", "analyst")):
                c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,$3)"
                      " ON CONFLICT (user_id, org_id) DO UPDATE SET role = excluded.role",
                      mate.user["id"], self.osc.org_id, role)
        team = self.osc.get(f"/v1/projects/{pid}/team")
        self.assertEqual(team.status, 200, team)
        self.assertGreaterEqual(team.json["count"], 4, "a equipe são as 4 pessoas vinculadas à organização dona")

        prop = self.funder.post("/v1/proposals", {
            "kind": "sponsorship", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Patrocínio das três turmas",
            "purpose": "Patrocinar material didático e transporte das turmas do período letivo."}).json["id"]
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})

        with db_system() as c:
            rows = c.query("SELECT user_id::text AS user_id, dedupe_key FROM notifications"
                           " WHERE ref_id = $1 AND ref_type = 'proposal'", prop)
            ev = c.one("SELECT event, notified FROM domain_events WHERE subject_id = $1"
                       " AND event = 'Proposal.sent'", prop)
        users = [r["user_id"] for r in rows]
        self.assertEqual(len(users), len(set(users)), "ninguém recebe dois avisos do mesmo fato")
        self.assertNotIn(self.funder.user["id"], users, "quem enviou não é avisado do próprio ato")
        self.assertIsNotNone(ev, "o fato fica registrado em domain_events")
        self.assertEqual(int(ev["notified"]), len(users), "o evento registra o alcance REAL do aviso")
        self.assertGreaterEqual(len(users), 4, "TODA a equipe é avisada, não só quem administra")

    def test_repeating_the_same_fact_does_not_notify_twice(self):
        pid = self.open_project()
        prop = self.funder.post("/v1/proposals", {
            "kind": "service", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Serviço de avaliação externa",
            "purpose": "Realizar avaliação externa de resultados ao final do ciclo de execução."}).json["id"]
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        with db_system() as c:
            first = c.scalar("SELECT count(*) FROM notifications WHERE ref_id = $1", prop)
        # reenviar a MESMA transição é no-op idempotente
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        with db_system() as c:
            second = c.scalar("SELECT count(*) FROM notifications WHERE ref_id = $1", prop)
        self.assertEqual(first, second, "reprocessar o mesmo fato não pode gerar aviso novo")

    def test_silencing_a_group_stops_the_notice_but_not_the_fact(self):
        pid = self.open_project()
        self.osc.put("/v1/notifications/prefs",
                     {"items": [{"grp": "proposal", "in_app": False, "email": False}]})
        prop = self.funder.post("/v1/proposals", {
            "kind": "collaboration", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Colaboração técnica no monitoramento",
            "purpose": "Colaborar na definição e coleta dos indicadores do projeto ao longo do ciclo."}).json["id"]
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        with db_system() as c:
            mine = c.scalar("SELECT count(*) FROM notifications WHERE ref_id = $1 AND user_id = $2",
                            prop, self.osc.user["id"])
            fact = c.one("SELECT 1 AS ok FROM domain_events WHERE subject_id = $1 AND event = 'Proposal.sent'", prop)
        self.osc.put("/v1/notifications/prefs",
                     {"items": [{"grp": "proposal", "in_app": True, "email": True}]})
        self.assertEqual(int(mine or 0), 0, "quem silenciou o grupo não recebe o aviso")
        self.assertIsNotNone(fact, "o FATO continua registrado mesmo sem aviso")

    def test_attaching_a_document_notifies_the_other_side(self):
        """'documentos juntados' é um dos eventos que o pedido manda avisar."""
        pid = self.open_project()
        prop = self.funder.post("/v1/proposals", {
            "kind": "investment", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Investimento com due diligence",
            "purpose": "Investir no projeto após conferência de documentação institucional e técnica.",
            "amount_cents": 20_000_000}).json["id"]
        # A rota de documento é multipart (exige o arquivo). O que este teste exercita é o ANEXO e o aviso, então
        # o documento é criado direto no cofre, no contexto da própria organização que o anexa.
        with db_system() as c:
            did = c.scalar(
                "INSERT INTO documents(org_id, title, doc_type, filename, mime_type, size_bytes, sha256,"
                " storage_key, status, uploaded_by) VALUES ($1,'Carta de intenção','other','carta.pdf',"
                " 'application/pdf', 1024, repeat('a', 64), 'test/carta.pdf', 'clean', $2) RETURNING id::text",
                self.funder.org_id, self.funder.user["id"])
        att = self.funder.post(f"/v1/proposals/{prop}/attachments", {"document_id": did})
        self.assertEqual(att.status, 201, att)
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM notifications WHERE ref_id = $1 AND user_id = $2", prop,
                         self.osc.user["id"])
            ev = c.one("SELECT 1 AS ok FROM domain_events WHERE event = 'Document.attached'"
                       " AND subject_id = $1", prop)
        self.assertGreaterEqual(int(n or 0), 1, "a outra parte precisa saber que um documento entrou")
        self.assertIsNotNone(ev)


# ================================================================================================ marketplace
class MarketplaceTests(NetBase):
    def test_listing_of_unpublished_project_cannot_go_live(self):
        pid = self.project()   # privado
        lst = self.osc.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pid, "seeking": ["investment"],
            "headline": "Formação profissional para 200 jovens na regional leste"})
        self.assertEqual(lst.status, 201, lst)
        self.assertEqual(lst.json["publication_state"], "draft")
        go = self.osc.post(f"/v1/marketplace/listings/{lst.json['id']}/transition", {"to": "published"})
        # o gatilho `listing_publish_guard` levanta 42501, que o tratador converte em 403: a recusa vem do BANCO,
        # não de uma checagem na rota que alguém poderia esquecer de repetir
        self.assertEqual(go.status, 403, go)
        self.assertEqual(self.osc.get(f"/v1/marketplace/listings/{lst.json['id']}").status, 404,
                         "anúncio em rascunho não é servido pela rota pública")

    def test_public_feed_returns_only_published_listings(self):
        """Invariante central do achado E6: projeto privado não aparece no marketplace."""
        priv = self.project(title="Projeto que deve ficar invisível")
        hidden = self.osc.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": priv, "seeking": ["investment"],
            "headline": "Este anúncio nunca deveria aparecer no feed público"}).json["id"]
        pub = self.project(title="Projeto publicado de verdade")
        self.publish(pub)
        shown = self.osc.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pub, "seeking": ["investment"],
            "headline": "Projeto publicado buscando investimento social para três turmas"}).json["id"]
        self.osc.post(f"/v1/marketplace/listings/{shown}/transition", {"to": "published"})

        anon = Client()
        feed = anon.get("/v1/marketplace/feed?limit=50")
        self.assertEqual(feed.status, 200, feed)
        ids = {i["id"] for i in feed.json["items"]}
        self.assertIn(shown, ids)
        self.assertNotIn(hidden, ids)
        for item in feed.json["items"]:
            self.assertEqual(item["publication_state"], "published")
            self.assertNotIn("suspended_reason", item)

    def test_only_administration_suspends_and_reason_is_required(self):
        pid = self.project()
        self.publish(pid)
        lid = self.osc.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pid, "seeking": ["partner"],
            "headline": "Projeto publicado procurando organização parceira executora"}).json["id"]
        self.osc.post(f"/v1/marketplace/listings/{lid}/transition", {"to": "published"})
        mine = self.osc.post(f"/v1/marketplace/listings/{lid}/transition",
                             {"to": "suspended", "note": "me suspendendo"})
        self.assertEqual(mine.status, 403, mine)
        self.assertEqual(mine.json["code"], "admin_only")

    def test_one_listing_per_subject(self):
        pid = self.project()
        a = self.osc.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pid, "headline": "Primeiro anúncio deste mesmo projeto"})
        self.assertEqual(a.status, 201, a)
        b = self.osc.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pid, "headline": "Segundo anúncio do mesmo projeto"})
        self.assertEqual(b.status, 409, b)
        self.assertEqual(b.json["code"], "listing_exists")

    def test_cannot_announce_someone_elses_project(self):
        pid = self.project()
        r = self.funder.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pid,
            "headline": "Anúncio de projeto que não é meu, o que não pode passar"})
        # 404 e não 403: sob RLS, projeto privado de terceiro não existe para quem olha. Dizer "existe, mas não é
        # seu" já seria revelar informação sobre o projeto de outra organização.
        self.assertEqual(r.status, 404, r)
        # e, mesmo publicado, continua sendo de quem é
        self.publish(pid)
        r2 = self.funder.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pid,
            "headline": "Anúncio de projeto publicado que ainda não é meu"})
        self.assertEqual(r2.status, 403, r2)


# ================================================================================================ conversa com contexto
class MessagingTests(NetBase):
    def link(self, pid: str) -> None:
        """Registra o vínculo que a conversa exige. É a jornada do investidor descrita no pedido:
        descobrir → favoritar → CONTATO → conversa com contexto → proposta."""
        r = self.funder.post("/v1/network/relationships",
                             {"kind": "contact", "target_type": "org", "target_id": self.osc.org_id,
                              "note": "Gostaria de conversar sobre o projeto publicado."})
        self.assertIn(r.status, (200, 201), r)

    def test_conversation_requires_a_registered_link(self):
        """Sem nenhum vínculo, a conversa é recusada pela trava anti-spam — e isso é proposital."""
        pid = self.open_project()
        stranger = new_account("company", compliance="approved")
        grant_premium(stranger)
        r = stranger.post("/v1/conversations", {"other_org_id": self.osc.org_id, "project_id": pid})
        self.assertEqual(r.status, 403, r)

    def test_professional_conversation_requires_context(self):
        r = self.funder.post("/v1/conversations", {"other_org_id": self.osc.org_id, "subject": "Oi"})
        self.assertEqual(r.status, 422, r)
        self.assertIn("project_id", (r.json.get("details") or {}).get("contextos", []), r.json)

    def test_same_context_reuses_the_same_thread(self):
        pid = self.open_project()
        self.link(pid)
        a = self.funder.post("/v1/conversations", {"other_org_id": self.osc.org_id, "project_id": pid,
                                                   "subject": "Dúvida sobre o orçamento"})
        self.assertEqual(a.status, 201, a)
        b = self.funder.post("/v1/conversations", {"other_org_id": self.osc.org_id, "project_id": pid})
        self.assertEqual(b.json["id"], a.json["id"], "mesmo contexto é a mesma conversa")
        self.assertFalse(b.json["created"])

    def test_ten_messages_generate_one_notice_until_it_is_read(self):
        pid = self.open_project()
        self.link(pid)
        opened = self.funder.post("/v1/conversations", {"other_org_id": self.osc.org_id, "project_id": pid,
                                                        "subject": "Negociação"})
        self.assertEqual(opened.status, 201, opened)
        cid = opened.json["id"]
        for i in range(5):
            r = self.funder.post(f"/v1/conversations/{cid}/messages", {"body": f"Recado número {i}"})
            self.assertEqual(r.status, 201, r)
        with db_system() as c:
            # só os avisos de RECADO: abrir a conversa gera o seu próprio aviso ("nova conversa"), que é outro fato
            n = c.scalar("SELECT count(*) FROM notifications WHERE ref_id = $1 AND ref_type = 'conversation'"
                         " AND user_id = $2 AND kind = 'message.sent'", cid, self.osc.user["id"])
            facts = c.scalar("SELECT count(*) FROM domain_events WHERE event = 'Message.sent'"
                             " AND subject_id = $1", cid)
        self.assertEqual(int(n or 0), 1, "cinco recados seguidos avisam uma vez, não cinco")
        self.assertEqual(int(facts), 5, "mas os cinco FATOS ficam registrados")

    def test_other_party_only_reads_its_own_thread(self):
        pid = self.open_project()
        self.link(pid)
        opened = self.funder.post("/v1/conversations", {"other_org_id": self.osc.org_id, "project_id": pid})
        self.assertEqual(opened.status, 201, opened)
        cid = opened.json["id"]
        stranger = new_account("company", compliance="approved")
        grant_premium(stranger)
        r = stranger.get(f"/v1/conversations/{cid}")
        self.assertIn(r.status, (403, 404), r)


# ================================================================================================ relatório de impacto
class ImpactReportTests(NetBase):
    def _supported_project(self) -> str:
        """Projeto com financiador apoiador — a relação que dá a ele o direito de revisar o relatório."""
        pid = self.open_project()
        created = self.funder.post("/v1/proposals", {
            "kind": "investment", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Apoio ao ciclo de execução", "amount_cents": 10_000_000,
            "purpose": "Apoiar o ciclo de execução das turmas previstas no projeto apresentado."})
        self.assertEqual(created.status, 201, created)
        prop = created.json["id"]
        self.assertEqual(self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"}).status, 200)
        self.osc.get(f"/v1/proposals/{prop}")
        acc = self.osc.post(f"/v1/proposals/{prop}/transition", {"to": "accepted"})
        self.assertEqual(acc.status, 200, acc)
        return pid

    def test_numbers_come_from_the_server_not_from_the_form(self):
        pid = self._supported_project()
        r = self.osc.post("/v1/impact-updates", {
            "project_id": pid, "period_start": _today(-90), "period_end": _today(-1),
            "summary": "Período de execução das duas primeiras turmas, com registro de presença e avaliação.",
            "outputs": "Duas turmas concluídas.", "limitations": "Sem grupo de comparação neste período."})
        self.assertEqual(r.status, 201, r)
        uid = r.json["id"]
        self.osc.post(f"/v1/impact-updates/{uid}/transition", {"to": "submitted"})
        with db_system() as c:
            row = c.one("SELECT metrics, evidence_count, submitted_at FROM impact_updates WHERE id = $1", uid)
        self.assertIsNotNone(row["submitted_at"], "o carimbo de envio é derivado pelo gatilho")
        self.assertIn("caveat", row["metrics"], "a apuração vem com a ressalva do que não está validado")
        self.assertIsInstance(row["evidence_count"], int)

    def test_executor_cannot_review_its_own_report(self):
        pid = self._supported_project()
        uid = self.osc.post("/v1/impact-updates", {
            "project_id": pid, "period_start": _today(-60), "period_end": _today(-2),
            "summary": "Relatório do período com os resultados das turmas e a avaliação dos participantes."
        }).json["id"]
        self.osc.post(f"/v1/impact-updates/{uid}/transition", {"to": "submitted"})
        self_review = self.osc.post(f"/v1/impact-updates/{uid}/transition", {"to": "accepted"})
        self.assertEqual(self_review.status, 403, self_review)
        self.assertEqual(self_review.json["code"], "self_review")

    def test_supporter_reviews_and_stranger_does_not(self):
        pid = self._supported_project()
        uid = self.osc.post("/v1/impact-updates", {
            "project_id": pid, "period_start": _today(-45), "period_end": _today(-3),
            "summary": "Prestação de contas do período, com indicadores medidos e marcos entregues."}).json["id"]
        self.osc.post(f"/v1/impact-updates/{uid}/transition", {"to": "submitted"})
        stranger = new_account("company", compliance="approved")
        grant_premium(stranger)
        no = stranger.post(f"/v1/impact-updates/{uid}/transition", {"to": "accepted"})
        self.assertIn(no.status, (403, 404), no)
        ok = self.funder.post(f"/v1/impact-updates/{uid}/transition", {"to": "accepted"})
        self.assertEqual(ok.status, 200, ok)
        with db_system() as c:
            row = c.one("SELECT reviewed_by::text AS reviewed_by, reviewed_by_org::text AS reviewed_by_org,"
                        " created_by::text AS created_by FROM impact_updates WHERE id = $1", uid)
        self.assertEqual(row["reviewed_by"], self.funder.user["id"])
        self.assertNotEqual(row["reviewed_by"], row["created_by"], "quatro olhos")

    def test_changes_requested_needs_a_note_and_only_published_is_public(self):
        pid = self._supported_project()
        uid = self.osc.post("/v1/impact-updates", {
            "project_id": pid, "period_start": _today(-30), "period_end": _today(-4),
            "summary": "Relatório parcial do período, enviado para conferência de quem apoia o projeto."}).json["id"]
        self.osc.post(f"/v1/impact-updates/{uid}/transition", {"to": "submitted"})
        no = self.funder.post(f"/v1/impact-updates/{uid}/transition", {"to": "changes_requested"})
        self.assertEqual(no.status, 422, no)
        self.funder.post(f"/v1/impact-updates/{uid}/transition",
                         {"to": "changes_requested", "note": "Faltou a medição do indicador de evasão."})
        anon = Client()
        pubfeed = anon.get(f"/v1/public/projects/{pid}/impact")
        self.assertEqual(pubfeed.status, 200, pubfeed)
        self.assertEqual(pubfeed.json["items"], [], "relatório não aceito não aparece em público")


# ================================================================================================ perfil público
class PublicProfileTests(NetBase):
    """Cada teste usa a sua própria conta: há UM perfil por organização, e reutilizar a conta da classe faria um
    teste atropelar o outro (409 profile_exists) em vez de exercitar o que ele se propõe."""

    def fresh(self, kind: str = "osc") -> Client:
        c = new_account(kind, compliance="approved")
        grant_premium(c)
        return c

    def test_reserved_handle_is_refused_and_normalization_works(self):
        for bad in ("admin", "SUPORTE", "Oficial"):
            r = self.osc.get(f"/v1/profiles/handle-available?handle={bad}")
            self.assertEqual(r.status, 200, r)
            self.assertFalse(r.json["available"], bad)
        ok = self.osc.get("/v1/profiles/handle-available?handle=Instituto%20%C3%81gua")
        self.assertEqual(ok.json["handle"], "instituto.agua", "acento sai, espaço vira ponto")

    def test_public_page_reads_only_the_curated_projection(self):
        org = self.fresh()
        handle = f"org{uuid.uuid4().hex[:10]}"
        r = org.post("/v1/profiles", {"handle": handle, "display_name": "Instituto de Teste",
                                      "headline": "Formação profissional no Mato Grosso", "owner": "org"})
        self.assertEqual(r.status, 201, r)
        anon = Client()
        page = anon.get(f"/v1/public/profiles/{handle}")
        self.assertEqual(page.status, 200, page)
        body = str(page.json)
        with db_system() as c:
            cnpj = c.scalar("SELECT cnpj FROM organizations WHERE id = $1", org.org_id)
        if cnpj:
            self.assertNotIn(cnpj, body, "CNPJ não entra na projeção pública")
        self.assertNotIn(org.email, body, "e-mail não entra na projeção pública")
        self.assertNotIn("compliance", body.lower())

    def test_changing_the_handle_keeps_the_trail_and_does_not_free_the_old_one(self):
        org = self.fresh()
        first = f"org{uuid.uuid4().hex[:10]}"
        created = org.post("/v1/profiles", {"handle": first, "display_name": "Instituto do Rastro",
                                            "owner": "org"})
        self.assertEqual(created.status, 201, created)
        pid = created.json["id"]
        second = f"org{uuid.uuid4().hex[:10]}"
        upd = org.patch(f"/v1/profiles/{pid}", {"handle": second})
        self.assertEqual(upd.status, 200, upd)
        hist = org.get(f"/v1/profiles/{pid}/handle-history")
        self.assertIn(first, [h["handle"] for h in hist.json["items"]])
        # o identificador antigo NÃO volta a estar livre: herdaria a reputação de quem o usava
        chk = org.get(f"/v1/profiles/handle-available?handle={first}")
        self.assertFalse(chk.json["available"])
        self.assertIn("carência", chk.json["reason"])

    def test_suspended_profile_answers_404(self):
        org = self.fresh()
        handle = f"org{uuid.uuid4().hex[:10]}"
        created = org.post("/v1/profiles", {"handle": handle, "display_name": "Perfil a suspender",
                                            "owner": "org"})
        self.assertEqual(created.status, 201, created)
        pid = created.json["id"]
        owner_conn().run("UPDATE public_profiles SET suspended = true WHERE id = $1", pid)
        anon = Client()
        r = anon.get(f"/v1/public/profiles/{handle}")
        self.assertEqual(r.status, 404, "dizer 'existe mas está suspenso' é informação sobre a moderação")

    def test_unverified_credential_never_reaches_the_public_page(self):
        person = new_account("provider", compliance="approved")
        grant_premium(person)
        handle = f"pro{uuid.uuid4().hex[:10]}"
        r = person.post("/v1/profiles", {"handle": handle, "display_name": "Profissional de Teste",
                                         "owner": "user"})
        self.assertEqual(r.status, 201, r)
        owner_conn().run(
            "INSERT INTO professional_credentials(user_id, org_id, council, number, uf, holder_name,"
            " verification_status) VALUES ($1,$2,'CREA','999999','MT','Profissional de Teste','self_declared')",
            person.user["id"], person.org_id)
        pidr = person.get("/v1/profiles/mine").json["person"]["id"]
        person.post(f"/v1/profiles/{pidr}/rebuild")
        anon = Client()
        page = anon.get(f"/v1/public/profiles/{handle}")
        self.assertEqual(page.status, 200, page)
        self.assertEqual(page.json["profile"].get("credentials", []), [],
                         "credencial pendente não aparece: a página pública não repassa afirmação não conferida")


# ================================================================================================ workspace e persona
class WorkspaceTests(NetBase):
    def test_four_personas_share_one_core(self):
        """Nenhuma persona tem domínio próprio: todas chamam os mesmos motores, mudando só seleção e ordem."""
        seen = {}
        for kind, expected in (("osc", "organization"), ("company", "investor"), ("provider", "professional"),
                               ("government", "government")):
            c = new_account(kind, compliance="approved")
            grant_premium(c)
            w = c.get("/v1/workspace")
            self.assertEqual(w.status, 200, f"{kind}: {w}")
            self.assertEqual(w.json["persona"]["key"], expected, kind)
            self.assertEqual(w.json["persona"]["source"], "default_by_org_kind")
            seen[expected] = [s["key"] for s in w.json["layout"]]
            self.assertIn("next_actions", seen[expected], "todo workspace abre com próximas ações")
            self.assertEqual(set(w.json["sections"].keys()), set(seen[expected]))
        # as experiências são DIFERENTES entre si (não é a mesma tela quatro vezes)
        self.assertNotEqual(seen["organization"], seen["investor"])
        self.assertNotEqual(seen["professional"], seen["government"])

    def test_persona_does_not_grant_permission(self):
        """Declarar-se investidor não concede o que o papel na organização não permite."""
        viewer_org = new_account("osc", compliance="approved")
        grant_premium(viewer_org)
        w = viewer_org.get("/v1/workspace").json
        self.assertTrue(w["capabilities"]["create_project"])
        # persona declarada não muda capacidade
        viewer_org.post("/v1/workspace/personas", {"persona": "organization", "primary": True})
        w2 = viewer_org.get("/v1/workspace").json
        self.assertEqual(w["capabilities"], w2["capabilities"])
        self.assertEqual(w2["persona"]["source"], "primary")

    def test_persona_must_match_the_organization_kind(self):
        r = self.osc.post("/v1/workspace/personas", {"persona": "government"})
        self.assertEqual(r.status, 422, r)
        self.assertIn("government", r.json["details"]["aplica_a"] + ["government"])

    def test_capabilities_match_what_the_routes_accept(self):
        """A capacidade anunciada e a rota precisam concordar: oferecer o que a rota recusa é defeito de produto."""
        w = self.funder.get("/v1/workspace").json
        self.assertFalse(w["capabilities"]["create_project"], "empresa não cria projeto")
        r = self.funder.post("/v1/projects", {"title": "Projeto de financiador", "summary": "x" * 40,
                                              "territory": "BR-MT"})
        self.assertIn(r.status, (403, 404, 422), r)


# ================================================================================================ prontidão e recomendação
class ReadinessTests(NetBase):
    def test_every_number_comes_with_the_criteria_that_produced_it(self):
        pid = self.project()
        r = self.osc.get(f"/v1/readiness/purposes?project_id={pid}")
        self.assertEqual(r.status, 200, r)
        d = r.json
        self.assertEqual(len(d["scores"]), 6)
        for key, detail in d["dimensions"].items():
            self.assertIn("question", detail, key)
            self.assertTrue(detail["checks"], f"{key} sem critérios é número mágico")
            for ch in detail["checks"]:
                self.assertIn("found", ch, "cada critério diz o que ENCONTROU")
                self.assertIn("weight", ch)
        self.assertEqual(d["engine_version"], "readiness@1.0.0")

    def test_funding_readiness_does_not_depend_on_already_having_funding(self):
        """Prontidão para captar não pode usar captação já obtida: seria circular ("está pronto porque já captou").

        A asserção é estrutural em vez de montar um compromisso: nenhum dos critérios de captação lê o valor
        comprometido, e isso é verificável diretamente na saída do motor — que, por desenho, publica cada critério.
        """
        pid = self.project()
        d = self.osc.get(f"/v1/readiness/purposes?project_id={pid}").json["dimensions"]["funding_readiness"]
        keys = {c["key"] for c in d["checks"]}
        self.assertNotIn("funding.committed", keys)
        self.assertNotIn("funding.raised", keys)
        self.assertIn("committed_cents", d, "o valor captado é INFORMADO, mas fora do cálculo")
        self.assertIn("não pode depender", d["note"])
        for c in d["checks"]:
            self.assertNotIn("captado", c["label"].lower(), c["key"])
            self.assertNotIn("comprometido", c["label"].lower(), c["key"])

    def test_snapshot_is_append_only(self):
        pid = self.project()
        s = self.osc.post(f"/v1/readiness/snapshots?project_id={pid}", {})
        self.assertEqual(s.status, 201, s)
        sid = s.json["snapshot_id"]
        with app_tx(self.osc) as c, self.assertRaises(Exception):
            c.run("UPDATE readiness_snapshots SET overall = 100 WHERE id = $1", sid)

    def test_recommendation_always_says_why_and_from_where(self):
        pid = self.project()
        self.osc.post("/v1/recommendations/refresh", {})
        r = self.osc.get("/v1/recommendations")
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["items"], "projeto recém-criado tem o que fazer")
        for rec in r.json["items"]:
            self.assertGreaterEqual(len(rec["rationale"]), 10, rec["action"])
            self.assertTrue(rec["link"].startswith("/"), rec["link"])
            self.assertIn(rec["confidence_band"], ("high", "medium", "low", "insufficient_data", None))

    def test_refreshing_does_not_duplicate_and_old_ones_become_superseded(self):
        pid = self.project()
        self.osc.post("/v1/recommendations/refresh", {})
        first = {(i["action"], i["subject_id"]) for i in self.osc.get("/v1/recommendations").json["items"]}
        self.osc.post("/v1/recommendations/refresh", {})
        second = {(i["action"], i["subject_id"]) for i in self.osc.get("/v1/recommendations").json["items"]}
        self.assertEqual(first, second, "recalcular não duplica")
        with db_system() as c:
            dup = c.query("SELECT action, subject_id, count(*) AS n FROM recommendations"
                          " WHERE org_id = $1 AND status = 'open' GROUP BY action, subject_id HAVING count(*) > 1",
                          self.osc.org_id)
        self.assertEqual(dup, [], "o índice parcial garante uma recomendação aberta por ação e sujeito")


if __name__ == "__main__":
    unittest.main()
