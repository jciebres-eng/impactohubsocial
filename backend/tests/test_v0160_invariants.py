"""Invariantes da REDE. São as afirmações que não podem deixar de valer entre versões.

Cada uma corresponde a uma promessa do pedido desta rodada, e está escrita de forma que quebrá-la faça um teste
falhar — não apenas contradizer um parágrafo da documentação:

  1. a existência de uma relação não implica que ela seja visível;
  2. bloqueio, favorito e acompanhamento são SEMPRE privados;
  3. nada nasce publicado, aceito ou enviado;
  4. proposta aceita cria relação e intenção, nunca compromisso nem dinheiro;
  5. quem propõe não aceita; quem executa não revisa o próprio relatório;
  6. projeto privado nunca aparece no marketplace;
  7. a página pública lê só a projeção curada;
  8. um fato gera um aviso por pessoa, e nunca avisa quem agiu;
  9. silenciar aviso não apaga o fato;
 10. número de relatório é apurado, não digitado;
 11. estimativa de pessoas exige fonte declarada;
 12. grupo beneficiário é atributo de projeto/necessidade, nunca filtro de pessoa;
 13. recomendação sempre diz por quê;
 14. preço é do servidor, com vigência, e aumento exige aviso;
 15. histórico não se reescreve.
"""
from __future__ import annotations

import datetime as dt
import unittest
import uuid

from impacto.network import marketplace as MK
from impacto.network import profiles as PRO
from impacto.network import proposals as PR
from impacto.network import relationships as REL
from tests.support import Client, db_system, grant_premium, new_account


def _d(n: int = 0) -> str:
    return (dt.date.today() + dt.timedelta(days=n)).isoformat()


# ================================================================================================ unidade
class VocabularyInvariants(unittest.TestCase):
    """O vocabulário tem de impedir o erro, não apenas descrevê-lo."""

    def test_block_favorite_and_watchlist_can_never_be_public(self):
        for kind in ("block", "favorite", "watchlist"):
            for asked in REL.VISIBILITY:
                got = REL.cap_visibility(kind, asked)
                self.assertFalse(REL.at_least(got, "network"),
                                 f"{kind} aceitou visibilidade {asked} → {got}")

    def test_every_relationship_kind_declares_its_accepted_targets(self):
        for kind in REL.KINDS:
            self.assertIn(kind, REL.TARGETS, kind)
            self.assertTrue(REL.TARGETS[kind], kind)

    def test_consented_kinds_are_disjoint_from_unilateral(self):
        self.assertEqual(set(REL.UNILATERAL) & set(REL.CONSENTED), set())
        self.assertEqual(set(REL.UNILATERAL) & set(REL.PARTICIPATION), set())

    def test_relationship_state_machine_has_no_way_out_of_closed(self):
        for closed in REL.CLOSED:
            self.assertEqual(REL.TRANSITIONS[closed], (),
                             f"{closed} precisa ser terminal: relação encerrada não ressuscita")

    def test_proposal_closed_states_are_terminal_except_changes_requested(self):
        self.assertIn("changes_requested", PR.OPEN)
        for st in PR.CLOSED:
            self.assertNotIn(st, PR.OPEN, st)

    def test_marketplace_has_exactly_one_public_state(self):
        self.assertEqual(MK.PUBLIC_STATES, ("published",),
                         "mais de um estado público significaria dois caminhos para expor conteúdo")

    def test_public_projection_is_a_closed_list_without_private_fields(self):
        keys = {k for k, _, _ in PRO.PROJECTABLE}
        for never in PRO.NEVER_PUBLIC:
            self.assertFalse(any(never in k for k in keys), never)

    def test_handle_normalization_is_idempotent_and_strips_accents(self):
        for raw in ("Instituto Água", "instituto  agua", "INSTITUTO-AGUA", "  instituto_agua  "):
            once = PRO.normalize(raw)
            self.assertEqual(once, PRO.normalize(once), raw)
            self.assertTrue(PRO.HANDLE_RE.match(once), f"{raw} → {once}")
            self.assertNotIn("á", once)


# ================================================================================================ integração
class NetworkInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.funder = new_account("company", compliance="approved")
        grant_premium(cls.osc)
        grant_premium(cls.funder)

    def project(self, publish: bool = False) -> str:
        r = self.osc.post("/v1/projects", {
            "title": f"Projeto invariante {uuid.uuid4().hex[:6]}",
            "summary": "Resumo suficiente para avaliação por terceiros neste teste de invariante.",
            "problem": "Problema descrito com evidência local e fonte declarada no diagnóstico.",
            "objectives": "Objetivo geral e específicos declarados para o período previsto.",
            "methodology": "Oficinas semanais com registro de presença e avaliação por módulo.",
            "territory": "BR-MT", "budget_total_cents": 20_000_000, "causes": ["educacao"], "ods": [4],
            "beneficiaries_count": 150, "beneficiaries_description": "Jovens da regional leste"})
        self.assertEqual(r.status, 201, r)
        pid = r.json["id"]
        if publish:
            self.assertIn(self.osc.post(f"/v1/projects/{pid}/publish", {}).status, (200, 201))
        return pid

    # ------------------------------------------------------------------ vocabulário compartilhado com o banco
    def test_python_vocabularies_match_the_database_checks(self):
        """Lista em Python e CHECK no banco precisam dizer a MESMA coisa.

        Encontrado na v0.16.0: `notify.PRIORITIES` tinha 'urgent' e o CHECK de `notifications.priority` tem
        'critical'. A divergência passava por lint, por type-check e pela suíte inteira, e só apareceria na
        primeira notificação de prioridade máxima — que é o caminho da moderação. Este teste compara as listas que
        existem nos dois lados.
        """
        from impacto.network import enforcement as ENF
        from impacto.network import impact_report as IR
        from impacto.network import notify as NT

        def check_values(table: str, column: str) -> set[str]:
            with db_system() as c:
                defs = c.query(
                    "SELECT pg_get_constraintdef(con.oid) AS d FROM pg_constraint con"
                    " WHERE con.conrelid = $1::regclass AND con.contype = 'c'", table)
            import re as _re
            # Uma coluna pode ter VÁRIOS CHECKs. `publication_state`, por exemplo, tem o da lista de valores e
            # também `(publication_state = 'published') = (published_at IS NOT NULL)` — pegar o primeiro que
            # mencione a coluna devolveria {'published'} e o teste acusaria divergência onde não há. O que
            # interessa é o CHECK de DOMÍNIO, que é o de lista: o que tem mais valores.
            best: set[str] = set()
            for d in defs:
                if f"{column} =" not in d["d"] and f"({column})::text" not in d["d"]:
                    continue
                if "ANY (ARRAY" not in d["d"]:
                    continue
                vals = set(_re.findall(r"'([a-z_]+)'::text", d["d"]))
                if len(vals) > len(best):
                    best = vals
            if best:
                return best
            self.fail(f"não achei o CHECK de domínio de {table}.{column}")

        pairs = [
            (set(NT.PRIORITIES), check_values("notifications", "priority"), "notify.PRIORITIES"),
            (set(REL.KINDS), check_values("relationships", "kind"), "relationships.KINDS"),
            (set(REL.VISIBILITY), check_values("relationships", "visibility"), "relationships.VISIBILITY"),
            (set(REL.STATUSES), check_values("relationships", "status"), "relationships.STATUSES"),
            (set(PR.KINDS), check_values("proposals", "kind"), "proposals.KINDS"),
            (set(PR.STATUSES), check_values("proposals", "status"), "proposals.STATUSES"),
            (set(MK.STATES), check_values("marketplace_listings", "publication_state"), "marketplace.STATES"),
            (set(MK.SUBJECTS), check_values("marketplace_listings", "subject_type"), "marketplace.SUBJECTS"),
            (set(IR.STATUSES), check_values("impact_updates", "status"), "impact_report.STATUSES"),
            (set(ENF.MEASURES), check_values("enforcement_actions", "measure"), "enforcement.MEASURES"),
            (set(ENF.STATUSES), check_values("enforcement_actions", "status"), "enforcement.STATUSES"),
        ]
        for py, db, name in pairs:
            self.assertEqual(py, db, f"{name} divergiu do CHECK no banco")

    # ------------------------------------------------------------------ 1 e 2
    def test_relationship_existence_never_implies_visibility(self):
        pid = self.project(publish=True)
        for kind in ("favorite", "watchlist"):
            self.assertEqual(self.funder.post("/v1/network/relationships",
                                              {"kind": kind, "target_type": "project", "target_id": pid,
                                               "visibility": "public"}).status, 201)
        anon = Client().get(f"/v1/public/relationships/project/{pid}")
        self.assertEqual(anon.json["items"], [], "relação privada saiu pela rota pública")
        # e nem para quem está autenticado, porque o teto do tipo é 'private'
        logged = new_account("company", compliance="approved")
        self.assertEqual(logged.get(f"/v1/public/relationships/project/{pid}").json["items"], [])

    # ------------------------------------------------------------------ 3
    def test_nothing_is_born_published_accepted_or_sent(self):
        pid = self.project(publish=True)
        prop = self.funder.post("/v1/proposals", {
            "kind": "investment", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Proposta do invariante",
            "purpose": "Verificar que nada nasce enviado nesta plataforma."})
        self.assertEqual(prop.json["status"], "draft")
        lst = self.osc.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pid,
            "headline": "Anúncio do invariante, que precisa nascer em rascunho"})
        self.assertEqual(lst.json["publication_state"], "draft")
        upd = self.osc.post("/v1/impact-updates", {
            "project_id": pid, "period_start": _d(-30), "period_end": _d(-1),
            "summary": "Relatório do invariante, que precisa nascer em rascunho e não enviado."})
        self.assertEqual(upd.json["status"], "draft")

    # ------------------------------------------------------------------ 4
    def test_accepting_a_proposal_never_creates_money(self):
        pid = self.project(publish=True)
        prop = self.funder.post("/v1/proposals", {
            "kind": "investment", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Investimento do invariante", "amount_cents": 50_000_000,
            "purpose": "Verificar que aceitar proposta não cria compromisso nem recebimento."}).json["id"]
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        self.osc.get(f"/v1/proposals/{prop}")
        self.osc.post(f"/v1/proposals/{prop}/transition", {"to": "accepted"})
        with db_system() as c:
            f = c.one("SELECT committed_cents, confirmed_cents, disbursed_cents FROM project_funding($1)", pid)
            n_commit = c.scalar("SELECT count(*) FROM commitments WHERE project_id = $1", pid)
            intent = c.one("SELECT status, commitment_id FROM investment_intents"
                           " WHERE investor_org_id = $1 AND project_id = $2", self.funder.org_id, pid)
        self.assertEqual((int(f["committed_cents"] or 0), int(f["confirmed_cents"] or 0),
                          int(f["disbursed_cents"] or 0)), (0, 0, 0))
        self.assertEqual(int(n_commit or 0), 0, "não existe compromisso criado por aceite de proposta")
        self.assertEqual(intent["status"], "in_negotiation")
        self.assertIsNone(intent["commitment_id"], "intenção comprometida sem compromisso é proibida pelo CHECK")

    # ------------------------------------------------------------------ 5
    def test_the_proposer_never_decides_and_the_executor_never_reviews(self):
        pid = self.project(publish=True)
        prop = self.funder.post("/v1/proposals", {
            "kind": "sponsorship", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Patrocínio do invariante",
            "purpose": "Verificar que quem propõe não decide a própria proposta."}).json["id"]
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        for to in ("accepted", "declined", "changes_requested"):
            r = self.funder.post(f"/v1/proposals/{prop}/transition", {"to": to, "note": "tentativa do proponente"})
            self.assertIn(r.status, (403, 409), f"{to}: {r}")

    # ------------------------------------------------------------------ 6
    def test_a_private_project_can_never_reach_the_marketplace(self):
        priv = self.project()
        lid = self.osc.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": priv,
            "headline": "Anúncio de projeto privado, que não pode ir ao ar"}).json["id"]
        # a transição é recusada pelo BANCO, não por checagem de rota
        self.assertEqual(self.osc.post(f"/v1/marketplace/listings/{lid}/transition",
                                       {"to": "published"}).status, 403)
        # e mesmo forçando o estado com o dono do banco, a RLS do feed não o serve... então a prova é outra:
        # o feed público só devolve itens publicados, e verificamos isso item a item
        feed = Client().get("/v1/marketplace/feed?limit=50")
        self.assertNotIn(lid, [i["id"] for i in feed.json["items"]])
        for item in feed.json["items"]:
            self.assertEqual(item["publication_state"], "published")

    def test_only_the_marketplace_engine_filters_by_publication_state(self):
        """O filtro de publicação vive SÓ no motor do marketplace.

        A forma do invariante importa: não interessa quantas vezes a condição aparece dentro do motor (a listagem e
        a contagem precisam dela, e `view()` também), e sim que NENHUM outro módulo a escreva. Uma segunda cópia em
        outra rota é exatamente como um `WHERE` se perde — era o achado E6 da auditoria.
        """
        import ast
        import pathlib
        base = pathlib.Path(__file__).resolve().parents[1] / "impacto"
        offenders = []
        for f in list(base.glob("api/*.py")) + list(base.glob("network/*.py")) + list(base.glob("services/*.py")):
            if f.name == "marketplace.py":
                continue
            src = f.read_text(encoding="utf-8")
            # Linhas de DOCSTRING ficam de fora: explicar a regra em prosa é o oposto do problema. O que não pode
            # é a condição aparecer em código.
            doc_lines: set[int] = set()
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    d = ast.get_docstring(node, clean=False)
                    if d and node.body and isinstance(node.body[0], ast.Expr):
                        first = node.body[0]
                        doc_lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
            for i, line in enumerate(src.splitlines(), 1):
                if i in doc_lines:
                    continue
                code = line.split("#", 1)[0]
                if "publication_state" in code and "published" in code:
                    offenders.append(f"{f.name}:{i}")
        self.assertEqual(offenders, [],
                         f"filtro de publicação fora do motor do marketplace: {offenders}")

    # ------------------------------------------------------------------ 7
    def test_the_public_page_reads_only_the_curated_projection(self):
        org = new_account("osc", compliance="approved")
        grant_premium(org)
        handle = f"inv{uuid.uuid4().hex[:8]}"
        self.assertEqual(org.post("/v1/profiles", {"handle": handle, "display_name": "Instituto do Invariante",
                                                   "owner": "org"}).status, 201)
        page = Client().get(f"/v1/public/profiles/{handle}")
        self.assertEqual(page.status, 200, page)
        body = str(page.json).lower()
        with db_system() as c:
            o = c.one("SELECT cnpj, contact_email, compliance_status FROM organizations WHERE id = $1", org.org_id)
        for secret in (o["cnpj"], o["contact_email"], org.email):
            if secret:
                self.assertNotIn(str(secret).lower(), body, secret)
        self.assertNotIn("compliance", body)
        # a projeção gravada também não contém campo proibido
        with db_system() as c:
            fields = c.scalar("SELECT public_fields FROM public_profiles WHERE handle = $1", handle)
        flat = str(fields).lower()
        for never in PRO.NEVER_PUBLIC:
            self.assertNotIn(f'"{never}"', flat, never)

    # ------------------------------------------------------------------ 8 e 9
    def test_one_fact_one_notice_per_person_and_never_the_actor(self):
        pid = self.project(publish=True)
        prop = self.funder.post("/v1/proposals", {
            "kind": "collaboration", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Colaboração do invariante",
            "purpose": "Verificar que um fato gera um aviso por pessoa."}).json["id"]
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        with db_system() as c:
            rows = c.query("SELECT user_id::text AS user_id FROM notifications WHERE ref_id = $1", prop)
            ev = c.one("SELECT notified FROM domain_events WHERE subject_id = $1 AND event = 'Proposal.sent'", prop)
        users = [r["user_id"] for r in rows]
        self.assertEqual(len(users), len(set(users)))
        self.assertNotIn(self.funder.user["id"], users)
        self.assertEqual(int(ev["notified"]), len(users), "o evento registra o alcance real")

    def test_the_fact_survives_the_silenced_notice(self):
        pid = self.project(publish=True)
        self.osc.put("/v1/notifications/prefs", {"items": [{"grp": "proposal", "in_app": False, "email": False}]})
        prop = self.funder.post("/v1/proposals", {
            "kind": "service", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Serviço do invariante",
            "purpose": "Verificar que silenciar o aviso não apaga o fato."}).json["id"]
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        with db_system() as c:
            mine = c.scalar("SELECT count(*) FROM notifications WHERE ref_id = $1 AND user_id = $2",
                            prop, self.osc.user["id"])
            fact = c.one("SELECT 1 AS ok FROM domain_events WHERE subject_id = $1", prop)
        self.osc.put("/v1/notifications/prefs", {"items": [{"grp": "proposal", "in_app": True, "email": True}]})
        self.assertEqual(int(mine or 0), 0)
        self.assertIsNotNone(fact)

    # ------------------------------------------------------------------ 10
    def test_impact_numbers_are_gathered_not_typed(self):
        pid = self.project(publish=True)
        uid = self.osc.post("/v1/impact-updates", {
            "project_id": pid, "period_start": _d(-60), "period_end": _d(-1),
            "summary": "Relatório para verificar que o número do servidor não vem do formulário."}).json["id"]
        # o cliente não tem como enviar metrics: o esquema de entrada não aceita
        self.assertEqual(self.osc.patch(f"/v1/impact-updates/{uid}",
                                        {"metrics": {"beneficiarios": 99999}}).status, 422)
        self.osc.post(f"/v1/impact-updates/{uid}/transition", {"to": "submitted"})
        with db_system() as c:
            m = c.scalar("SELECT metrics FROM impact_updates WHERE id = $1", uid)
            same = c.scalar("SELECT app_impact_metrics($1,$2,$3)", pid, _d(-60), _d(-1))
        self.assertNotIn("beneficiarios", m)
        self.assertEqual(m.get("measurements"), same.get("measurements"),
                         "a prévia e o registrado vêm da mesma função")

    # ------------------------------------------------------------------ 11 e 12
    def test_a_people_estimate_always_carries_its_source(self):
        gov = new_account("government", compliance="approved")
        grant_premium(gov)
        self.assertEqual(gov.post("/v1/territory/needs", {
            "territory": "BR-MT", "title": "Necessidade sem fonte do número", "people_estimate": 500}).status, 422)
        # e nem pelo banco: o CHECK da tabela recusa
        with db_system() as c, self.assertRaises(Exception) as e:
            c.run("INSERT INTO territory_needs(territory, org_id, title, people_estimate)"
                  " VALUES ('BR-MT',$1,'Tentativa direta sem fonte',500)", gov.org_id)
        self.assertIn("territory_needs_check", str(e.exception))

    def test_beneficiary_group_is_never_a_filter_on_people(self):
        """O termo descreve PROJETO ou NECESSIDADE. A política está no banco, e nenhuma rota o aceita como filtro."""
        tax = self.osc.get("/v1/taxonomies?taxonomy=beneficiary_group")
        self.assertEqual(tax.status, 200, tax)
        item = tax.json["items"][0]
        self.assertEqual(item["sensitivity"], "beneficiary_group")
        for word in ("filtrar", "segmentar", "inferir"):
            self.assertIn(word, item["usage_policy"].lower(), word)
        # Nenhuma rota aceita o grupo como critério de BUSCA (`query`). Registrá-lo como atributo de uma
        # necessidade (`body`) é o uso legítimo e previsto — a diferença entre os dois é exatamente o ponto.
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        for r in ROUTES:
            if r.query is None:
                continue
            for field in r.query.model_fields:
                self.assertNotIn("beneficiary_group", field,
                                 f"{r.method} {r.path} aceita grupo beneficiário como filtro de busca")
        # E o atributo existe apenas onde descreve a NECESSIDADE, nunca uma pessoa.
        with db_system() as c:
            cols = c.query(
                "SELECT table_name FROM information_schema.columns"
                " WHERE column_name = 'beneficiary_groups' AND table_schema = 'public'")
        self.assertEqual({x["table_name"] for x in cols}, {"territory_needs"},
                         "grupo beneficiário só pode descrever a necessidade do território")

    # ------------------------------------------------------------------ 13
    def test_every_recommendation_explains_itself(self):
        self.project()
        self.osc.post("/v1/recommendations/refresh", {})
        items = self.osc.get("/v1/recommendations").json["items"]
        self.assertTrue(items)
        for r in items:
            self.assertGreaterEqual(len(r["rationale"]), 10, r["action"])
            self.assertTrue(r["link"].startswith("/"), r["action"])
            self.assertIsInstance(r["evidence"], dict)
            if r["confidence"] is not None:
                self.assertIn(r["confidence_band"], ("high", "medium", "low", "insufficient_data"))

    # ------------------------------------------------------------------ 14
    def test_price_comes_from_the_server_with_an_effective_period(self):
        q = Client().get("/v1/plans/price?plan_key=osc_premium&interval=month")
        self.assertEqual(q.status, 200, q)
        self.assertIn("currency", q.json)
        self.assertIn("tax_note", q.json)
        # A moeda vem do produto (`monetization.DEFAULT_CURRENCY`), não está fixa no teste: a v0.17.0
        # voltou de USD para BRL e o invariante é "UMA vigente", não "uma vigente em dólar".
        from impacto.services.monetization import DEFAULT_CURRENCY
        self.assertEqual(q.json["currency"], DEFAULT_CURRENCY)
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM plan_price_versions WHERE plan_key = 'osc_premium'"
                         " AND interval = 'month' AND currency = $1 AND effective_until IS NULL",
                         DEFAULT_CURRENCY)
        self.assertEqual(int(n), 1, "exatamente uma versão vigente por plano, intervalo e moeda")

    # ------------------------------------------------------------------ 15
    def test_history_is_never_rewritten(self):
        pid = self.project(publish=True)
        prop = self.funder.post("/v1/proposals", {
            "kind": "mentorship", "receiver_org_id": self.osc.org_id, "project_id": pid,
            "title": "Mentoria do invariante",
            "purpose": "Verificar que histórico de proposta não se reescreve."}).json["id"]
        self.funder.post(f"/v1/proposals/{prop}/transition", {"to": "sent"})
        with db_system() as c:
            eid = c.scalar("SELECT id FROM proposal_events WHERE proposal_id = $1 ORDER BY id LIMIT 1", prop)
            with self.assertRaises(Exception):
                c.run("UPDATE proposal_events SET note = 'reescrito' WHERE id = $1", eid)
            with self.assertRaises(Exception):
                c.run("DELETE FROM proposal_events WHERE id = $1", eid)
            with self.assertRaises(Exception):
                c.run("UPDATE domain_events SET notified = 0 WHERE subject_id = $1", prop)

    def test_handle_history_keeps_the_trail(self):
        org = new_account("osc", compliance="approved")
        grant_premium(org)
        first, second = f"h{uuid.uuid4().hex[:9]}", f"h{uuid.uuid4().hex[:9]}"
        pid = org.post("/v1/profiles", {"handle": first, "display_name": "Perfil do rastro",
                                        "owner": "org"}).json["id"]
        self.assertEqual(org.patch(f"/v1/profiles/{pid}", {"handle": second}).status, 200)
        hist = org.get(f"/v1/profiles/{pid}/handle-history").json["items"]
        self.assertIn(first, [h["handle"] for h in hist])
        with db_system() as c, self.assertRaises(Exception):
            c.run("DELETE FROM handle_history WHERE profile_id = $1", pid)


# ================================================================================================ isolamento
class CrossTenantNetworkMatrix(unittest.TestCase):
    """Nenhuma rota de escrita da rede aceita identificador de outra organização.

    A varredura da v0.15.0 cobre identificador INEXISTENTE. Esta cobre o caso mais perigoso: identificador que
    existe, mas é de outra organização — onde um `WHERE org_id` esquecido vazaria de verdade.
    """

    @classmethod
    def setUpClass(cls):
        cls.a = new_account("osc", compliance="approved")
        cls.b = new_account("osc", compliance="approved")
        cls.co = new_account("company", compliance="approved")
        for c in (cls.a, cls.b, cls.co):
            grant_premium(c)

    def _own(self):
        def ok(r, what):
            self.assertIn(r.status, (200, 201), f"{what}: {r}")
            return r.json
        r = self.a.post("/v1/projects", {
            "title": f"Projeto de A {uuid.uuid4().hex[:6]}", "summary": "Resumo do projeto de A para a matriz.",
            "problem": "Problema do território descrito para a matriz de isolamento.",
            "objectives": "Objetivo declarado.", "methodology": "Oficinas semanais.",
            "territory": "BR-MT", "budget_total_cents": 1_000_000, "causes": ["educacao"],
            "beneficiaries_count": 10, "beneficiaries_description": "Público do teste"})
        pid = ok(r, "projeto de A")["id"]
        ok(self.a.post(f"/v1/projects/{pid}/publish", {}), "publicação")
        lid = ok(self.a.post("/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pid,
            "headline": "Anúncio de A para a matriz de isolamento entre inquilinos"}), "anúncio")["id"]
        prop = ok(self.co.post("/v1/proposals", {
            "kind": "investment", "receiver_org_id": self.a.org_id, "project_id": pid,
            "title": "Proposta para A", "purpose": "Proposta usada na matriz de isolamento."}), "proposta")["id"]
        ok(self.co.post(f"/v1/proposals/{prop}/transition", {"to": "sent"}), "envio da proposta")
        upd = ok(self.a.post("/v1/impact-updates", {
            "project_id": pid, "period_start": _d(-30), "period_end": _d(-1),
            "summary": "Relatório de A usado na matriz de isolamento entre inquilinos."}), "relatório")["id"]
        rel = ok(self.a.post("/v1/network/relationships",
                             {"kind": "favorite", "target_type": "project", "target_id": pid}), "relação")["id"]
        # Um perfil por organização: se A já tem (outro teste da classe criou), reaproveita o que existe.
        existing = self.a.get("/v1/profiles/mine").json.get("org")
        prof = existing["id"] if existing else ok(self.a.post(
            "/v1/profiles", {"handle": f"a{uuid.uuid4().hex[:9]}", "display_name": "Perfil de A",
                             "owner": "org"}), "perfil")["id"]
        return {"project": pid, "listing": lid, "proposal": prop, "update": upd, "rel": rel, "profile": prof}

    def test_b_cannot_touch_anything_of_a(self):
        own = self._own()
        cases: list[tuple[str, str, dict | None]] = [
            ("POST", f"/v1/marketplace/listings/{own['listing']}/transition", {"to": "published"}),
            ("PATCH", f"/v1/marketplace/listings/{own['listing']}", {"headline": "sequestro do anúncio de A"}),
            ("POST", f"/v1/proposals/{own['proposal']}/transition", {"to": "accepted"}),
            ("PATCH", f"/v1/proposals/{own['proposal']}", {"title": "sequestro da proposta"}),
            ("POST", f"/v1/proposals/{own['proposal']}/attachments", {"document_id": own["project"]}),
            ("PATCH", f"/v1/impact-updates/{own['update']}", {"summary": "sequestro do relatório de A" * 3}),
            ("POST", f"/v1/impact-updates/{own['update']}/transition", {"to": "submitted"}),
            ("POST", f"/v1/network/relationships/{own['rel']}/transition",
             {"to": "ended", "reason": "sequestro da relação"}),
            ("PUT", f"/v1/network/relationships/{own['rel']}/visibility", {"visibility": "public"}),
            ("PATCH", f"/v1/profiles/{own['profile']}", {"display_name": "sequestro do perfil"}),
            ("POST", f"/v1/profiles/{own['profile']}/rebuild", {}),
            ("GET", f"/v1/projects/{own['project']}/relatorios", None),
        ]
        leaks = []
        for method, path, body in cases:
            r = self.b.request(method, path, body)
            if 200 <= r.status < 300:
                leaks.append(f"{method} {path} -> {r.status}")
        self.assertEqual(leaks, [], "rotas que aceitaram identificador de outra organização:\n" + "\n".join(leaks))

    def test_b_cannot_read_a_proposal_it_is_not_part_of(self):
        own = self._own()
        for client, expect_ok in ((self.a, True), (self.co, True), (self.b, False)):
            r = client.get(f"/v1/proposals/{own['proposal']}")
            if expect_ok:
                self.assertEqual(r.status, 200, r)
            else:
                self.assertIn(r.status, (403, 404), r)

    def test_b_never_sees_a_private_relationship_of_a(self):
        own = self._own()
        mine = self.b.get("/v1/network/relationships?limit=100").json["items"]
        self.assertNotIn(own["rel"], [r["id"] for r in mine])


if __name__ == "__main__":
    unittest.main()
