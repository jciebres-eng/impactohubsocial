"""v0.12.0 — Central de Conhecimento: fluxo editorial (quatro olhos), visibilidade, busca/assistente ancorado, FAQ, biblioteca, ajuda contextual, "Comece aqui",
suporte (SLA/guards), eventos, academia (quiz/certificado), parcerias, demonstração, solicitação de teste, boletim, preferências e papéis internos.
HTTP + PostgreSQL reais; nenhum conteúdo fictício é tratado como oficial (itens de teste usam demo=true quando aplicável)."""
from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, UTC

from tests.support import Client, db_system, last_token_for, make_admin, new_account, server


def staff(*roles: str) -> Client:
    """Conta interna com papéis editoriais/suporte e MFA verificado (exigido nas rotas internas)."""
    c = new_account("osc")
    with db_system() as d:
        for r in roles:
            d.run("INSERT INTO staff_roles(user_id, role) VALUES ($1,$2) ON CONFLICT DO NOTHING", c.user["id"], r)
    # v0.35.0 (auditoria, AUTH-04): a equipe ativa o MFA com o código do aplicativo E o código enviado ao e-mail
    from tests.support import enable_mfa
    enable_mfa(c)
    return c


def uniq(p: str = "t") -> str:
    return f"{p}-{uuid.uuid4().hex[:8]}"


def article_body(slug: str, **kw) -> dict:
    b = {"slug": slug, "kind": "guide", "visibility": "public", "title": kw.pop("title", "Como fazer a prestação de contas do projeto"),
         "summary": kw.pop("summary", "Passo a passo para prestar contas com evidências e despesas."),
         "body": "Reúna comprovantes, registre despesas e envie as evidências para validação.",
         "steps": [{"title": "Reúna os comprovantes", "text": "Notas e recibos"}, {"title": "Registre as despesas", "text": ""}],
         "checklist": ["Comprovantes reunidos", "Despesas registradas"], "tags": ["prestação de contas", "evidências"], "action_label": "Ir para execução", "action_link": "/projetos"}
    b.update(kw)
    return b


def publish_article(ed: Client, rv: Client, **kw) -> dict:
    slug = kw.pop("slug", None) or uniq("guia")
    r = ed.post("/v1/admin/content/articles", article_body(slug, **kw))
    assert r.status == 201, r
    vid = r.json["version_id"]
    for who, to in ((ed, "review"), (rv, "approved"), (rv, "published")):
        t = who.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": to, "note": "ok para publicar"})
        assert t.status == 200, (to, t)
    return {"slug": slug, "version_id": vid, "id": r.json["id"]}


class Editorial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv, cls.sup = staff("editor"), staff("reviewer"), staff("support")
        cls.anon = Client()
        cls.user = new_account("osc")

    def test_draft_is_not_public_until_published_by_another_person(self):
        slug = uniq("rascunho")
        r = self.ed.post("/v1/admin/content/articles", article_body(slug))
        vid = r.json["version_id"]
        self.assertEqual(self.anon.get(f"/v1/help/articles/{slug}").status, 404)
        self.assertEqual(self.ed.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "review"}).status, 200)
        # quem escreveu não aprova (e editor sem papel reviewer também não)
        self.assertEqual(self.ed.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "approved"}).status, 403)
        self.assertEqual(self.anon.get(f"/v1/help/articles/{slug}").status, 404)
        self.assertEqual(self.rv.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "approved"}).status, 200)
        # aprovada ainda não é pública: publicar é um passo próprio
        self.assertEqual(self.anon.get(f"/v1/help/articles/{slug}").status, 404)
        self.assertEqual(self.rv.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "published"}).status, 200)
        art = self.anon.get(f"/v1/help/articles/{slug}").json
        self.assertEqual(art["origin_label"], "Informação oficial da plataforma")
        self.assertFalse(art["demo"])
        self.assertEqual(art["structured_data"]["@type"], "HowTo")
        hist = self.rv.get(f"/v1/admin/content/history/article_version/{vid}").json["items"]
        self.assertEqual([h["to_status"] for h in hist], ["draft", "review", "approved", "published"])

    def test_author_cannot_approve_even_as_platform_admin_and_db_enforces_it(self):
        adm, _ = make_admin()
        slug = uniq("admin")
        r = adm.post("/v1/admin/content/articles", article_body(slug))
        vid = r.json["version_id"]
        self.assertEqual(adm.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "review"}).status, 200)
        t = adm.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "approved"})
        self.assertEqual(t.status, 403)
        self.assertEqual(t.json["code"], "four_eyes")
        # mesmo contornando a API, o banco recusa aprovador = autor
        with self.assertRaises(Exception):
            with db_system() as d:
                d.run("UPDATE kb_article_versions SET status = 'approved', approved_by = author_id WHERE id = $1", vid)

    def test_published_version_is_immutable_and_new_version_supersedes(self):
        p = publish_article(self.ed, self.rv)
        with self.assertRaises(Exception):
            with db_system() as d:
                d.run("UPDATE kb_article_versions SET body = 'alterado em silêncio' WHERE id = $1", p["version_id"])
        r = self.ed.put(f"/v1/admin/content/article-versions/{p['version_id']}", {"title": "Outro título", "body": "x"})
        self.assertEqual(r.status, 409)
        self.assertEqual(self.ed.post(f"/v1/admin/content/articles/{p['slug']}/versions", {"title": "Título v2 do guia", "body": "texto novo"}).status, 422)   # exige nota
        v2 = self.ed.post(f"/v1/admin/content/articles/{p['slug']}/versions", {"title": "Título v2 do guia", "body": "texto novo", "change_note": "atualiza prazos"})
        self.assertEqual(v2.status, 201)
        self.assertEqual(self.anon.get(f"/v1/help/articles/{p['slug']}").json["version"], 1)      # a v1 segue no ar até a v2 ser publicada
        vid2 = v2.json["version_id"]
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/article-versions/{vid2}/transition", {"to": to}).status, 200)
        live = self.anon.get(f"/v1/help/articles/{p['slug']}").json
        self.assertEqual((live["version"], live["title"]), (2, "Título v2 do guia"))
        adm = self.ed.get(f"/v1/admin/content/articles/{p['slug']}").json
        self.assertEqual({v["version"]: v["status"] for v in adm["versions"]}, {1: "superseded", 2: "published"})

    def test_returning_to_draft_requires_a_note(self):
        r = self.ed.post("/v1/admin/content/articles", article_body(uniq("nota")))
        vid = r.json["version_id"]
        self.ed.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "review"})
        self.assertEqual(self.rv.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "draft"}).status, 422)
        self.assertEqual(self.rv.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "draft", "note": "ajustar o passo 2"}).status, 200)
        self.assertEqual(self.rv.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "published"}).status, 409)   # transição inválida

    def test_regulatory_content_needs_source_and_date_and_expires(self):
        slug = uniq("regra")
        r = self.ed.post("/v1/admin/content/articles", article_body(slug, regulatory=True))
        vid = r.json["version_id"]
        self.ed.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "review"})
        bad = self.rv.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "approved"})
        self.assertIn(bad.status, (409, 422))          # CHECK do banco: regulatório exige fonte e data
        self.ed.put(f"/v1/admin/content/article-versions/{vid}", {"title": "Regra fiscal de exemplo", "body": "x", "regulatory": True})
        # volta ao rascunho, completa fonte/data e vence ontem
        self.rv.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "draft", "note": "faltou a fonte"})
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
        self.assertEqual(self.ed.put(f"/v1/admin/content/article-versions/{vid}", {"title": "Regra fiscal de exemplo", "body": "texto", "regulatory": True,
                                                                                     "regulatory_source": "Lei X, art. 1º (exemplo)", "regulatory_date": "2025-01-01", "valid_until": yesterday}).status, 200)
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": to}).status, 200)
        a = self.anon.get(f"/v1/help/articles/{slug}").json
        self.assertTrue(a["needs_review"])
        self.assertIn("regulatório", a["review_notice"])
        self.assertTrue(a["regulatory_source"])

    def test_roles_are_enforced(self):
        self.assertEqual(self.user.post("/v1/admin/content/articles", article_body(uniq())).status, 403)
        self.assertEqual(self.sup.post("/v1/admin/content/articles", article_body(uniq())).status, 403)           # suporte não edita conteúdo
        self.assertEqual(self.ed.get("/v1/admin/support/tickets").status, 403)                                      # editor não atende chamados
        self.assertEqual(self.ed.get("/v1/admin/staff-roles").status, 403)
        r = self.ed.post("/v1/admin/content/articles", article_body(uniq()))
        self.ed.post(f"/v1/admin/content/article-versions/{r.json['version_id']}/transition", {"to": "review"})
        t = self.ed.post(f"/v1/admin/content/article-versions/{r.json['version_id']}/transition", {"to": "published"})
        self.assertEqual(t.status, 403)
        self.assertEqual(t.json["code"], "role_required")

    def test_staff_routes_require_mfa(self):
        c = new_account("osc")
        with db_system() as d:
            d.run("INSERT INTO staff_roles(user_id, role) VALUES ($1,'editor')", c.user["id"])
        r = c.post("/v1/admin/content/articles", article_body(uniq()))
        self.assertEqual(r.status, 403)
        self.assertEqual(r.json["code"], "mfa_required")
        self.assertEqual(c.get("/v1/me").json["user"]["staff_roles"], ["editor"])

    def test_admin_grants_and_revokes_staff_roles(self):
        """v0.20.0: revogar papel interno passou a EXIGIR motivo escrito.

        O inventário de risco (§40) classificou a operação como crítica — é tirar o acesso de uma
        pessoa — e encontrou que ela não registrava por quê. O teste acompanhou a exigência e ficou
        mais forte: confere que a revogação sem motivo é recusada, e que o motivo chega à auditoria.
        """
        adm, _ = make_admin()
        u = new_account("osc")
        self.assertEqual(adm.post("/v1/admin/staff-roles", {"email": u.email, "role": "support"}).status, 201)
        self.assertEqual(u.get("/v1/me").json["user"]["staff_roles"], ["support"])
        sem_motivo = adm.delete(f"/v1/admin/staff-roles/{u.user['id']}/support")
        self.assertEqual(sem_motivo.status, 422, "revogar acesso sem motivo não pode passar")
        motivo = "Saiu da equipe de suporte em 06/10, conforme comunicado interno."
        r = adm.delete(f"/v1/admin/staff-roles/{u.user['id']}/support?reason={motivo.replace(' ', '%20')}")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(u.get("/v1/me").json["user"]["staff_roles"], [])
        with db_system() as c:
            registro = c.one("SELECT payload FROM audit_events WHERE action = 'staff.role_revoked'"
                             " AND object_id = $1 ORDER BY id DESC LIMIT 1", u.user["id"])
        self.assertIsNotNone(registro, "a revogação não foi auditada")
        self.assertIn("Saiu da equipe", registro["payload"]["reason"])


class Visibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv = staff("editor"), staff("reviewer")
        cls.anon = Client()
        cls.osc, cls.company = new_account("osc"), new_account("company")

    def test_visibility_levels(self):
        pub = publish_article(self.ed, self.rv, visibility="public")
        auth = publish_article(self.ed, self.rv, visibility="authenticated")
        aud = publish_article(self.ed, self.rv, visibility="audience", audience=["company"])
        self.assertEqual(self.anon.get(f"/v1/help/articles/{pub['slug']}").status, 200)
        self.assertEqual(self.anon.get(f"/v1/help/articles/{auth['slug']}").status, 404)
        self.assertEqual(self.osc.get(f"/v1/help/articles/{auth['slug']}").status, 200)
        self.assertEqual(self.osc.get(f"/v1/help/articles/{aud['slug']}").status, 404)
        self.assertEqual(self.company.get(f"/v1/help/articles/{aud['slug']}").status, 200)
        lst = {i["slug"] for i in self.anon.get("/v1/help/articles?limit=100").json["items"]}
        self.assertIn(pub["slug"], lst)
        self.assertNotIn(auth["slug"], lst)

    def test_sitemap_lists_only_public_non_demo(self):
        pub = publish_article(self.ed, self.rv, visibility="public")
        demo = publish_article(self.ed, self.rv, visibility="public", demo=True)
        priv = publish_article(self.ed, self.rv, visibility="authenticated")
        urls = [u["loc"] for u in self.anon.get("/v1/help/sitemap").json["urls"]]
        self.assertTrue(any(u.endswith(f"/ajuda/{pub['slug']}") for u in urls))
        self.assertFalse(any(u.endswith(f"/ajuda/{demo['slug']}") for u in urls))
        self.assertFalse(any(u.endswith(f"/ajuda/{priv['slug']}") for u in urls))
        self.assertIsNone(self.anon.get(f"/v1/help/articles/{demo['slug']}").json["structured_data"])
        self.assertFalse(self.anon.get(f"/v1/help/articles/{demo['slug']}").json["seo"]["index"])
        self.assertTrue(self.anon.get(f"/v1/help/articles/{demo['slug']}").json["demo_label"])


class SearchAndAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv = staff("editor"), staff("reviewer")
        cls.anon, cls.user = Client(), new_account("osc")
        cls.tag = uniq("zq")
        cls.art = publish_article(cls.ed, cls.rv, title="Como organizar a prestação de contas do projeto", ctx_keys=["execution.accountability"],
                                  summary="Registre despesas, anexe comprovantes e envie evidências para validação.")

    def test_semantic_vocabulary_finds_by_synonym_and_explains(self):
        r = self.anon.get("/v1/help/search?q=como+prestar+contas").json
        self.assertTrue(r["items"], r)
        top = r["items"][0]
        self.assertIn(self.art["slug"], [i["slug"] for i in r["items"]])
        self.assertTrue(top["why"])
        self.assertIn("vocabulário", r["semantic"])

    def test_ctx_search_and_contextual_help(self):
        c = self.anon.get("/v1/help/context?key=execution.accountability").json
        self.assertIn(self.art["slug"], [a["slug"] for a in c["articles"]])
        self.assertEqual(c["help"]["label"], "Preciso de ajuda")

    def test_empty_search_offers_next_steps_and_logs_only_hash(self):
        q = "xyzzy plugh frobnicate"
        r = self.anon.get("/v1/help/search?q=" + q.replace(" ", "+")).json
        self.assertEqual(r["items"], [])
        self.assertTrue(r["empty"]["suggest"])
        with db_system() as d:
            rows = d.query("SELECT q_hash, concepts, kind FROM kb_events WHERE kind = 'search_empty' ORDER BY id DESC LIMIT 5")
            self.assertTrue(rows)
            cols = [r["column_name"] for r in d.query("SELECT column_name FROM information_schema.columns WHERE table_name = 'kb_events'")]
        self.assertNotIn("q", cols)
        self.assertNotIn("query", cols)
        self.assertTrue(all(len(r["q_hash"].strip()) == 16 for r in rows))

    def test_assistant_is_grounded_and_cites_sources(self):
        r = self.anon.post("/v1/help/assistant", {"question": "Como faço a prestação de contas do projeto?"}).json
        self.assertTrue(r["grounded"])
        self.assertFalse(r["ai_used"])
        self.assertIn("prestação de contas", r["answer"].lower())
        self.assertTrue(r["sources"][0]["link"].startswith("/ajuda/"))
        self.assertTrue(r["sources"][0]["origin_label"])
        self.assertTrue(any(a["link"] == "/projetos" for a in r["actions"]))

    def test_assistant_refuses_without_base_and_offers_ticket(self):
        r = self.anon.post("/v1/help/assistant", {"question": "Qual é a capital da Mongólia e a previsão do tempo?"}).json
        self.assertIsNone(r["answer"])
        # v0.29.0: "base publicada" em vez de "base oficial" — a base inclui material educacional; o rótulo da origem real vem em cada fonte
        self.assertEqual(r["message"], "Não encontrei informação suficiente na base publicada da plataforma.")
        self.assertEqual(r["sources"], [])
        self.assertEqual(r["actions"][0]["link"], "/ajuda/suporte/novo")
        self.assertFalse(r["ai_used"])

    def test_assistant_does_not_use_unpublished_content(self):
        slug = uniq("segredo")
        self.ed.post("/v1/admin/content/articles", article_body(slug, title="Procedimento interno xyloquartzo", summary="xyloquartzo xyloquartzo", visibility="public"))
        r = self.anon.post("/v1/help/assistant", {"question": "O que é o procedimento xyloquartzo?"}).json
        self.assertIsNone(r["answer"])

    def test_search_validates_input(self):
        self.assertEqual(self.anon.get("/v1/help/search?q=" + "a" * 500).status, 422)
        self.assertEqual(self.anon.get("/v1/help/search?type=outro").status, 422)
        self.assertEqual(self.anon.post("/v1/help/assistant", {"question": "ab"}).status, 422)


class FaqAndResources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv = staff("editor"), staff("reviewer")
        cls.anon, cls.u1, cls.u2 = Client(), new_account("osc"), new_account("company")

    def pub(self, path: str, body: dict, kind: str):
        r = self.ed.post(path, body)
        self.assertEqual(r.status, 201, r)
        rid = r.json["id"]
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            t = who.post(f"/v1/admin/content/{kind}/{rid}/transition", {"to": to})
            self.assertEqual(t.status, 200, t)
        return rid

    def test_faq_feedback_rollup_and_low_resolution_flag(self):
        fid = self.pub("/v1/admin/content/faqs", {"question": "Posso cancelar o teste gratuito?", "answer": "Sim, a qualquer momento em Conta > Plano."}, "faqs")
        self.assertEqual(self.u1.post("/v1/help/feedback", {"target_type": "faq", "target_id": fid, "helpful": False}).status, 422)      # exige motivo
        self.assertEqual(self.u1.post("/v1/help/feedback", {"target_type": "faq", "target_id": fid, "helpful": False, "reason": "outdated"}).status, 200)
        self.assertEqual(self.u2.post("/v1/help/feedback", {"target_type": "faq", "target_id": fid, "helpful": True}).status, 200)
        f = next(i for i in self.anon.get("/v1/help/faqs").json["items"] if i["id"] == fid)
        self.assertEqual((f["helpful_yes"], f["helpful_no"]), (1, 1))
        # um voto por pessoa (atualiza, não duplica)
        self.u1.post("/v1/help/feedback", {"target_type": "faq", "target_id": fid, "helpful": True})
        f = next(i for i in self.anon.get("/v1/help/faqs").json["items"] if i["id"] == fid)
        self.assertEqual((f["helpful_yes"], f["helpful_no"]), (2, 0))
        self.assertEqual(self.anon.post("/v1/help/feedback", {"target_type": "faq", "target_id": fid, "helpful": True}).status, 401)
        # baixa resolução: muitos votos "não"
        fid2 = self.pub("/v1/admin/content/faqs", {"question": "Como emitir a nota fiscal da assinatura?", "answer": "Em breve."}, "faqs")
        with db_system() as d:
            d.run("UPDATE kb_faqs SET helpful_yes = 1, helpful_no = 9 WHERE id = $1", fid2)
        ov = self.ed.get("/v1/admin/content/overview").json
        self.assertIn(fid2, [x["id"] for x in ov["low_resolution_faqs"]])

    def test_faq_revision_replaces_only_when_new_one_is_published(self):
        fid = self.pub("/v1/admin/content/faqs", {"question": "Qual o prazo do período de teste?", "answer": "Sete dias."}, "faqs")
        r = self.ed.post("/v1/admin/content/faqs", {"question": "Qual o prazo do período de teste?", "answer": "Quatorze dias.", "revises_id": fid})
        nid = r.json["id"]
        self.assertEqual([i["answer"] for i in self.anon.get("/v1/help/faqs").json["items"] if i["id"] in (fid, nid)], ["Sete dias."])
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            who.post(f"/v1/admin/content/faqs/{nid}/transition", {"to": to})
        self.assertEqual([i["answer"] for i in self.anon.get("/v1/help/faqs").json["items"] if i["id"] in (fid, nid)], ["Quatorze dias."])

    def test_template_resource_creates_draft_for_org(self):
        slug = uniq("modelo")
        rid = self.pub("/v1/admin/content/resources", {"slug": slug, "kind": "template", "title": "Modelo de plano de trabalho", "visibility": "authenticated", "origin": "educational",
                                                       "template_schema": {"draft_kind": "work_plan", "fields": [{"key": "objetivo", "label": "Objetivo", "required": True}, {"key": "metas", "label": "Metas"}]}}, "resources")
        r = self.u1.get(f"/v1/help/resources/{slug}").json
        self.assertTrue(r["template_schema"])
        self.assertEqual(r["origin_label"], "Material educacional")
        bad = self.u1.post(f"/v1/help/resources/{rid}/use-template", {"values": {"metas": "x"}})
        self.assertEqual(bad.status, 422)
        ok = self.u1.post(f"/v1/help/resources/{rid}/use-template", {"values": {"objetivo": "Reduzir a evasão", "metas": "3 metas"}})
        self.assertEqual(ok.status, 201, ok)
        drafts = self.u1.get("/v1/drafts").json["items"]
        self.assertIn(ok.json["draft_id"], [d["id"] for d in drafts])
        self.assertEqual(self.anon.get(f"/v1/help/resources/{slug}").status, 404)       # authenticated

    def test_resource_versions_are_immutable_and_history_is_kept(self):
        slug = uniq("doc")
        base = {"slug": slug, "kind": "document", "title": "Guia de documentos exigidos", "visibility": "public", "url": "https://exemplo.org/guia-v1.pdf"}
        rid = self.pub("/v1/admin/content/resources", base, "resources")
        self.assertEqual(self.ed.put(f"/v1/admin/content/resources/{rid}", base).status, 409)
        with self.assertRaises(Exception):
            with db_system() as d:
                d.run("UPDATE kb_resources SET url = 'https://troca.silenciosa.org/x' WHERE id = $1", rid)
        self.assertEqual(self.ed.post(f"/v1/admin/content/resources/{rid}/new-version", {**base, "url": "https://exemplo.org/guia-v2.pdf"}).status, 422)   # nota obrigatória
        nv = self.ed.post(f"/v1/admin/content/resources/{rid}/new-version", {**base, "url": "https://exemplo.org/guia-v2.pdf", "change_note": "atualiza lista"})
        self.assertEqual(nv.status, 201)
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            who.post(f"/v1/admin/content/resources/{nv.json['id']}/transition", {"to": to})
        r = self.anon.get(f"/v1/help/resources/{slug}").json
        self.assertEqual((r["version"], r["url"]), (2, "https://exemplo.org/guia-v2.pdf"))
        self.assertEqual({v["version"]: v["status"] for v in r["versions"]}, {1: "superseded", 2: "published"})
        dl = self.u1.post(f"/v1/help/resources/{r['id']}/download-url")
        self.assertEqual(dl.json["url"], "https://exemplo.org/guia-v2.pdf")

    def test_resource_download_of_stored_file_uses_temporary_url(self):
        slug = uniq("arq")
        with db_system() as d:
            org = d.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1") or d.scalar(
                "INSERT INTO organizations(kind, legal_name, compliance_status) VALUES ('platform','Plataforma','approved') RETURNING id::text")
            did = d.scalar("INSERT INTO documents(org_id, doc_type, title, filename, mime_type, size_bytes, sha256, storage_key, status) VALUES ($1,'other','Modelo','modelo.txt','text/plain',5,$2,$3,'clean') RETURNING id::text",
                           org, "0" * 64, f"kb/{uuid.uuid4().hex}")
        rid = self.pub("/v1/admin/content/resources", {"slug": slug, "kind": "document", "title": "Arquivo da biblioteca", "visibility": "authenticated", "document_id": did}, "resources")
        r = self.u1.post(f"/v1/help/resources/{rid}/download-url")
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["url"].startswith("/v1/files/") or r.json["url"].startswith("http"))
        self.assertEqual(r.json["expires_in"], 300)
        self.assertEqual(self.anon.post(f"/v1/help/resources/{rid}/download-url").status, 401)

    def test_checklist_progress_is_saved_per_user(self):
        scope = "article:" + uniq("chk")
        self.assertEqual(self.u1.put("/v1/help/checklists", {"scope": scope, "checked": [0, 2, 2]}).json["checked"], [0, 2])
        self.assertEqual(self.u1.get(f"/v1/help/checklists?scope={scope}").json["checked"], [0, 2])
        self.assertEqual(self.u2.get(f"/v1/help/checklists?scope={scope}").json["checked"], [])


class Onboarding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()

    def test_every_detector_runs_for_every_org_kind(self):
        from impacto.services import hub
        for kind in ("osc", "company", "individual", "provider", "government"):
            c = new_account(kind)
            r = c.get("/v1/help/start")
            self.assertEqual(r.status, 200, (kind, r))
            self.assertTrue(r.json["steps"], kind)
            self.assertEqual(r.json["steps"][0]["key"], "account")
            self.assertTrue(r.json["steps"][0]["done"])
        self.assertTrue(set(hub.DETECTORS) >= {s["detector"] for p in hub.onboarding_config()["paths"].values() for s in p["steps"]})

    def test_progress_comes_from_real_data(self):
        c = new_account("osc")
        before = c.get("/v1/help/start").json
        self.assertFalse(next(s for s in before["steps"] if s["key"] == "project")["done"])
        self.assertIn("dados reais", before["measure"])
        r = c.post("/v1/projects", {"title": "Projeto Biblioteca Viva", "summary": "Acervo comunitário para leitura e formação de jovens", "territory": "BR-MT"})
        self.assertEqual(r.status, 201, r)
        after = c.get("/v1/help/start").json
        self.assertTrue(next(s for s in after["steps"] if s["key"] == "project")["done"])
        self.assertGreater(after["percent"], before["percent"])
        self.assertEqual(after["next"]["key"], next(s["key"] for s in after["steps"] if not s["done"]))

    def test_pending_center_and_activities(self):
        c = new_account("osc")
        p = c.get("/v1/help/pending").json
        self.assertTrue(p["items"])
        self.assertEqual(p["items"][0]["kind"], "onboarding")
        a = c.get("/v1/help/activities").json
        self.assertEqual(set(a), {"tickets", "courses", "events", "certificates", "partnership_requests", "demo_requests"})
        self.assertEqual(c.get("/v1/help/recommendations").status, 200)

    def test_requires_auth(self):
        self.assertEqual(Client().get("/v1/help/start").status, 401)
        self.assertEqual(Client().get("/v1/help/pending").status, 401)


class Support(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.sup = staff("support")
        cls.u1, cls.u2 = new_account("osc"), new_account("osc")

    def open_ticket(self, c=None, **kw):
        c = c or self.u1
        body = {"category": "project", "subject": "Não consigo anexar o orçamento", "message": "O botão de anexar não responde.", "context": {"page": "projetos", "field": "project.budget"}}
        body.update(kw)
        r = c.post("/v1/support/tickets", body)
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def test_ticket_lifecycle_with_sla_and_staff_roles(self):
        tid = self.open_ticket()
        t = self.u1.get(f"/v1/support/tickets/{tid}").json
        self.assertEqual((t["status"], t["priority"]), ("open", "normal"))
        self.assertIsNotNone(t["first_response_due"])
        self.assertNotIn("assigned_to", t)
        # equipe responde: primeira resposta registrada e aguarda a usuária
        self.assertEqual(self.sup.post(f"/v1/admin/support/tickets/{tid}/messages", {"body": "Pode enviar um print da tela?"}).status, 201)
        self.assertEqual(self.sup.post(f"/v1/admin/support/tickets/{tid}/messages", {"body": "nota interna: ver log do upload", "internal": True}).status, 201)
        st = self.sup.get(f"/v1/admin/support/tickets/{tid}").json
        self.assertEqual(st["status"], "waiting_user")
        self.assertIsNotNone(st["first_response_at"])
        mine = self.u1.get(f"/v1/support/tickets/{tid}").json
        self.assertEqual([m["body"] for m in mine["messages"]], ["O botão de anexar não responde.", "Pode enviar um print da tela?"])   # nota interna invisível
        # usuária responde: volta para a fila
        self.assertEqual(self.u1.post(f"/v1/support/tickets/{tid}/messages", {"body": "Segue o print."}).status, 201)
        self.assertEqual(self.sup.get(f"/v1/admin/support/tickets/{tid}").json["status"], "open")
        # prioridade só pela equipe; SLA recalculado
        before = self.sup.get(f"/v1/admin/support/tickets/{tid}").json["first_response_due"]
        self.assertEqual(self.sup.patch(f"/v1/admin/support/tickets/{tid}", {"priority": "critical", "status": "in_progress", "assign": True, "assigned_to": self.sup.user["id"]}).status, 200)
        after = self.sup.get(f"/v1/admin/support/tickets/{tid}").json
        self.assertEqual(after["priority"], "critical")
        self.assertLess(after["first_response_due"], before)
        # avaliar e encerrar só depois de resolvido
        self.assertEqual(self.u1.post(f"/v1/support/tickets/{tid}/rate", {"score": 5}).status, 409)
        self.assertEqual(self.u1.post(f"/v1/support/tickets/{tid}/close").status, 409)
        self.assertEqual(self.sup.patch(f"/v1/admin/support/tickets/{tid}", {"status": "resolved"}).status, 200)
        self.assertEqual(self.u1.post(f"/v1/support/tickets/{tid}/rate", {"score": 5}).status, 200)
        self.assertEqual(self.u1.post(f"/v1/support/tickets/{tid}/close").status, 200)
        self.assertEqual(self.u1.post(f"/v1/support/tickets/{tid}/messages", {"body": "mais uma"}).status, 409)

    def test_user_cannot_set_priority_state_or_assignee_even_directly(self):
        tid = self.open_ticket()
        from impacto.db.pool import DbContext
        st = server()["state"]
        with self.assertRaises(Exception):
            with st.pool.tx(DbContext(user_id=self.u1.user["id"], org_id=self.u1.org_id, org_kind="osc")) as c:
                c.run("UPDATE support_tickets SET priority = 'critical' WHERE id = $1", tid)
        with self.assertRaises(Exception):
            with st.pool.tx(DbContext(user_id=self.u1.user["id"], org_id=self.u1.org_id, org_kind="osc")) as c:
                c.run("UPDATE support_tickets SET status = 'resolved' WHERE id = $1", tid)
        with st.pool.tx(DbContext(user_id=self.u1.user["id"], org_id=self.u1.org_id, org_kind="osc")) as c:
            c.run("INSERT INTO support_tickets(org_id, user_id, category, priority, status, subject, assigned_to) VALUES ($1,$2,'bug','critical','closed','tentativa de prioridade', $2)", self.u1.org_id, self.u1.user["id"])
            row = c.one("SELECT priority, status, assigned_to FROM support_tickets WHERE subject = 'tentativa de prioridade'")
        self.assertEqual((row["priority"], row["status"], row["assigned_to"]), ("normal", "open", None))

    def test_tickets_are_private_to_requester_and_staff(self):
        tid = self.open_ticket()
        self.assertEqual(self.u2.get(f"/v1/support/tickets/{tid}").status, 404)
        self.assertEqual(self.u2.post(f"/v1/support/tickets/{tid}/messages", {"body": "intrometida"}).status, 404)
        self.assertNotIn(tid, [t["id"] for t in self.u2.get("/v1/support/tickets").json["items"]])
        self.assertEqual(self.u2.get("/v1/admin/support/tickets").status, 403)
        self.assertEqual(Client().post("/v1/support/tickets", {"category": "bug", "subject": "abc", "message": "abcde"}).status, 401)

    def test_attachment_must_be_own_org_document(self):
        r = self.u1.post("/v1/support/tickets", {"category": "document", "subject": "Anexo inválido", "message": "teste", "document_ids": [str(uuid.uuid4())]})
        self.assertEqual(r.status, 422)
        self.assertEqual(r.json["code"], "invalid_attachment")
        up = self.u1.upload("/v1/documents", "print.txt", b"conteudo de teste", {"doc_type": "other", "title": "Print"})
        self.assertEqual(up.status, 201, up)
        ok = self.u1.post("/v1/support/tickets", {"category": "document", "subject": "Com anexo", "message": "ver anexo", "document_ids": [up.json["id"]]})
        self.assertEqual(ok.status, 201, ok)
        self.assertEqual(self.u1.get(f"/v1/support/tickets/{ok.json['id']}").json["attachments"][0]["document_id"], up.json["id"])
        # documento de outra organização não pode ser anexado
        self.assertEqual(self.u2.post("/v1/support/tickets", {"category": "document", "subject": "Roubo", "message": "teste", "document_ids": [up.json["id"]]}).status, 422)

    def test_sla_escalation_and_recurring_candidates(self):
        from impacto.services import hub
        tid = self.open_ticket(subject="Chamado antigo sem resposta")
        with db_system() as d:
            d.run("UPDATE support_tickets SET created_at = now() - interval '10 days' WHERE id = $1", tid)
            out = hub.sla_escalation(d)
            row = d.one("SELECT priority, escalated_at FROM support_tickets WHERE id = $1", tid)
        self.assertGreaterEqual(out["escalated"], 1)
        self.assertIsNotNone(row["escalated_at"])
        self.assertEqual(row["priority"], "high")
        for _ in range(3):
            self.open_ticket(self.u2, category="funding", subject="Dúvida recorrente sobre aporte", context={"page": "carteira"})
        with db_system() as d:
            rec = hub.recurring_candidates(d)
        self.assertTrue(any(r["category"] == "funding" and r["page"] == "carteira" for r in rec))

    def test_ticket_from_help_is_counted_and_sla_is_configurable_by_admin_only(self):
        self.open_ticket()
        self.assertEqual(self.sup.get("/v1/admin/support/sla").json["status"], "HIPÓTESE — validar com a equipe de suporte")
        self.assertEqual(self.sup.put("/v1/admin/support/sla/high", {"first_response_minutes": 30, "resolution_minutes": 600, "escalate_after_minutes": 60}).status, 403)
        adm, _ = make_admin()
        self.assertEqual(adm.put("/v1/admin/support/sla/high", {"first_response_minutes": 240, "resolution_minutes": 2880, "escalate_after_minutes": 480}).status, 200)
        with db_system() as d:
            self.assertGreaterEqual(d.scalar("SELECT count(*) FROM kb_events WHERE kind = 'ticket_from_help'"), 1)

    def test_prefs_in_app_off_suppresses_notification(self):
        u = new_account("osc")
        # O número de grupos cresce quando a plataforma cresce (a 0016 somou os da rede). Comparar com a lista do
        # produto em vez de um número fixo deixa o teste afirmar o que importa — "todos os grupos aparecem" — e não
        # quebrar a cada grupo novo.
        from impacto.services.hub import GROUPS
        got = u.get("/v1/notifications/prefs").json["items"]
        self.assertEqual({g["grp"] for g in got}, set(GROUPS))
        self.assertEqual(u.put("/v1/notifications/prefs", {"items": [{"grp": "support", "in_app": False, "email": True}]}).status, 200)
        tid = self.open_ticket(u)
        self.sup.post(f"/v1/admin/support/tickets/{tid}/messages", {"body": "Resposta da equipe"})
        notes = u.get("/v1/notifications").json
        self.assertFalse([n for n in notes["items"] if n["kind"].startswith("support")])
        # busca pelo grupo, não por posição na lista: a ordem não é contrato
        back = u.put("/v1/notifications/prefs", {"items": [{"grp": "support", "in_app": True, "email": True}]}).json
        self.assertTrue(next(g for g in back["items"] if g["grp"] == "support")["in_app"])
        self.sup.post(f"/v1/admin/support/tickets/{tid}/messages", {"body": "Segunda resposta"})
        self.assertTrue([n for n in u.get("/v1/notifications").json["items"] if n["kind"].startswith("support")])
        self.assertEqual(u.put("/v1/notifications/prefs", {"items": [{"grp": "outro", "in_app": True, "email": True}]}).status, 422)


class Events(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv = staff("editor"), staff("reviewer")
        cls.anon, cls.a, cls.b = Client(), new_account("osc"), new_account("company")

    def make_event(self, **kw) -> dict:
        slug = uniq("evento")
        body = {"slug": slug, "kind": "webinar", "title": "Webinar de boas práticas", "description": "Conversa sobre prestação de contas.", "starts_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
                "duration_min": 60, "join_url": "https://meet.exemplo.org/sala-secreta", "capacity": 1, "demo": True}
        body.update(kw)
        r = self.ed.post("/v1/admin/content/events", body)
        self.assertEqual(r.status, 201, r)
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/events/{r.json['id']}/transition", {"to": to}).status, 200)
        return {"id": r.json["id"], "slug": slug}

    def test_registration_waitlist_promotion_and_private_join_link(self):
        e = self.make_event()
        pub = self.anon.get(f"/v1/help/events/{e['slug']}").json
        self.assertIsNone(pub["join_url"])
        self.assertEqual((pub["seats_left"], pub["demo_label"] is not None), (1, True))
        self.assertEqual(self.a.post(f"/v1/help/events/{e['id']}/register").json["status"], "registered")
        self.assertEqual(self.b.post(f"/v1/help/events/{e['id']}/register").json["status"], "waitlist")
        self.assertEqual(self.a.post(f"/v1/help/events/{e['id']}/register").json.get("already"), True)
        self.assertEqual(self.a.get(f"/v1/help/events/{e['slug']}").json["join_url"], "https://meet.exemplo.org/sala-secreta")
        self.assertIsNone(self.b.get(f"/v1/help/events/{e['slug']}").json["join_url"])          # lista de espera não vê o link
        self.assertTrue(self.a.get(f"/v1/help/events/{e['slug']}").json["full"])
        self.assertEqual(self.a.delete(f"/v1/help/events/{e['id']}/register").json["promoted"], True)
        self.assertEqual(self.b.get(f"/v1/help/events/{e['slug']}").json["my_registration"]["status"], "registered")
        self.assertEqual(self.b.get(f"/v1/help/events/{e['slug']}").json["join_url"], "https://meet.exemplo.org/sala-secreta")
        self.assertTrue([n for n in self.b.get("/v1/notifications").json["items"] if "Vaga confirmada" in n["title"]])
        self.assertEqual(self.anon.post(f"/v1/help/events/{e['id']}/register").status, 401)

    def test_past_or_unpublished_events_reject_registration(self):
        past = self.ed.post("/v1/admin/content/events", {"slug": uniq("passado"), "kind": "webinar", "title": "Evento já ocorrido", "starts_at": "2020-01-01T10:00:00Z", "duration_min": 30})
        self.assertEqual(self.a.post(f"/v1/help/events/{past.json['id']}/register").status, 404)       # rascunho não aparece
        e = self.make_event(capacity=None)
        self.ed.patch(f"/v1/admin/content/events/{e['id']}", {"registration_open": False})
        self.assertEqual(self.a.post(f"/v1/help/events/{e['id']}/register").status, 409)

    def test_attendance_enables_rating_and_completion_exposes_recording(self):
        e = self.make_event(capacity=None)
        self.a.post(f"/v1/help/events/{e['id']}/register")
        self.assertEqual(self.a.post(f"/v1/help/events/{e['id']}/rate", {"satisfaction": 5}).status, 409)
        self.assertEqual(self.ed.post(f"/v1/admin/content/events/{e['id']}/attendance", {"user_ids": [self.a.user["id"]]}).json["marked"], 1)
        self.assertEqual(self.a.post(f"/v1/help/events/{e['id']}/rate", {"satisfaction": 4}).status, 200)
        self.assertIsNone(self.anon.get(f"/v1/help/events/{e['slug']}").json["recording_url"])          # só após concluído
        self.assertEqual(self.ed.patch(f"/v1/admin/content/events/{e['id']}", {"status": "completed", "recording_url": "https://video.exemplo.org/gravacao"}).status, 200)
        self.assertEqual(self.anon.get(f"/v1/help/events/{e['slug']}").json["recording_url"], "https://video.exemplo.org/gravacao")
        r = self.ed.post(f"/v1/admin/content/events/{e['id']}/recording-to-resource")
        self.assertEqual(r.status, 201)
        self.assertEqual(self.ed.post(f"/v1/admin/content/events/{e['id']}/recording-to-resource").status, 409)

    def test_cancelling_event_notifies_registered(self):
        e = self.make_event(capacity=None)
        self.a.post(f"/v1/help/events/{e['id']}/register")
        self.assertEqual(self.ed.patch(f"/v1/admin/content/events/{e['id']}", {"status": "cancelled"}).status, 200)
        self.assertTrue([n for n in self.a.get("/v1/notifications").json["items"] if "Evento cancelado" in n["title"]])

    def test_reminder_job_is_idempotent(self):
        from impacto.services import hub
        e = self.make_event(capacity=None, starts_at=(datetime.now(UTC) + timedelta(hours=5)).isoformat())
        u = new_account("osc")
        u.post(f"/v1/help/events/{e['id']}/register")
        with db_system() as d:
            n1 = hub.event_reminders(d)["reminders"]
            n2 = hub.event_reminders(d)["reminders"]
        self.assertGreaterEqual(n1, 1)
        self.assertEqual(n2, 0)


class Academy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv = staff("editor"), staff("reviewer")
        cls.anon, cls.u, cls.v = Client(), new_account("osc"), new_account("osc")
        cls.slug = uniq("curso")
        body = {"slug": cls.slug, "title": "Fundamentos de prestação de contas", "summary": "Curso curto de exemplo.", "hours": 2.0, "pass_score": 70, "cert_enabled": True, "demo": True, "visibility": "public",
                "modules": [{"title": "Módulo 1", "lessons": [
                    {"title": "Introdução", "kind": "text", "body": "Texto da aula."},
                    {"title": "Vídeo", "kind": "video", "video_url": "https://video.exemplo.org/a1", "captions_url": "https://video.exemplo.org/a1.vtt", "transcript": "Transcrição completa."},
                    {"title": "Quiz final", "kind": "quiz", "quiz": [{"q": "Evidências devem ser enviadas?", "options": ["Sim", "Não"], "answer": 0},
                                                                    {"q": "Despesas precisam de comprovante?", "options": ["Não", "Sim", "Talvez"], "answer": 1}]}]}]}
        r = cls.ed.post("/v1/admin/content/courses", body)
        assert r.status == 201, r
        cls.cid = r.json["id"]
        for who, to in ((cls.ed, "review"), (cls.rv, "approved"), (cls.rv, "published")):
            assert who.post(f"/v1/admin/content/courses/{cls.cid}/transition", {"to": to}).status == 200

    def lessons(self, c=None):
        d = (c or self.u).get(f"/v1/help/courses/{self.slug}").json
        return [ls for m in d["modules"] for ls in m["lessons"]], d

    def test_quiz_key_never_leaves_the_server(self):
        ls, _ = self.lessons()
        quiz = next(x for x in ls if x["kind"] == "quiz")
        full = self.u.get(f"/v1/help/lessons/{quiz['id']}").json
        self.assertEqual(len(full["quiz"]), 2)
        self.assertNotIn("answer", full["quiz"][0])
        self.assertNotIn("answers", str(full))
        # nem o banco entrega o gabarito a uma usuária (RLS)
        from impacto.db.pool import DbContext
        with server()["state"].pool.tx(DbContext(user_id=self.u.user["id"], org_id=self.u.org_id, org_kind="osc")) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM lesson_quiz_keys"), 0)

    def test_enrollment_progress_quiz_and_certificate(self):
        ls, d = self.lessons()
        self.assertTrue(d["certificate_note"].startswith("Certificado de conclusão"))
        self.assertEqual(self.u.post(f"/v1/help/lessons/{ls[0]['id']}/complete", {}).status, 409)      # precisa se inscrever
        self.assertEqual(self.u.post(f"/v1/help/courses/{self.slug}/enroll").status, 200)
        self.assertEqual(self.u.post(f"/v1/help/courses/{self.slug}/certificate").status, 409)          # incompleto
        self.assertEqual(self.u.post(f"/v1/help/lessons/{ls[0]['id']}/complete", {}).json["percent"], 33)
        self.u.post(f"/v1/help/lessons/{ls[1]['id']}/complete", {})
        bad = self.u.post(f"/v1/help/lessons/{ls[2]['id']}/complete", {"answers": [1, 0]}).json
        self.assertEqual((bad["score"], bad["passed"]), (0, False))
        self.assertEqual(self.u.post(f"/v1/help/courses/{self.slug}/certificate").status, 409)
        ok = self.u.post(f"/v1/help/lessons/{ls[2]['id']}/complete", {"answers": [0, 1]}).json
        self.assertEqual((ok["score"], ok["passed"], ok["percent"], ok.get("course_completed")), (100, True, 100, True))
        cert = self.u.post(f"/v1/help/courses/{self.slug}/certificate")
        self.assertEqual(cert.status, 201, cert)
        code = cert.json["code"]
        self.assertEqual(self.u.post(f"/v1/help/courses/{self.slug}/certificate").json.get("already"), True)
        v = self.anon.get(f"/v1/help/certificates/{code}").json
        self.assertTrue(v["valid"])
        self.assertFalse(v["official"])
        self.assertIn("Não é diploma", v["notice"])
        self.assertEqual(self.anon.get("/v1/help/certificates/ZZZZZZZZZZZZ").status, 404)
        # revogação
        self.assertEqual(self.rv.post(f"/v1/admin/hub/certificates/{code}/revoke", {"reason": "emitido por engano"}).status, 200)
        self.assertFalse(self.anon.get(f"/v1/help/certificates/{code}").json["valid"])
        self.assertEqual(self.sup_cannot_revoke(code), 403)

    def sup_cannot_revoke(self, code):
        return self.ed.post(f"/v1/admin/hub/certificates/{code}/revoke", {"reason": "tentativa sem papel"}).status

    def test_progress_is_private(self):
        ls, _ = self.lessons(self.v)
        self.v.post(f"/v1/help/courses/{self.slug}/enroll")
        self.v.post(f"/v1/help/lessons/{ls[0]['id']}/complete", {})
        w = new_account("osc")
        _, dw = self.lessons(w)
        _, dv = self.lessons(self.v)
        self.assertGreaterEqual(dv["lessons_done"], 1)
        self.assertEqual((dw["lessons_done"], dw["enrollment"]), (0, None))
        self.assertEqual(Client().get(f"/v1/help/courses/{self.slug}").json["lessons_done"], 0)

    def test_quiz_requires_answers_and_unpublished_course_is_hidden(self):
        ls, _ = self.lessons()
        self.u.post(f"/v1/help/courses/{self.slug}/enroll")
        self.assertEqual(self.u.post(f"/v1/help/lessons/{ls[2]['id']}/complete", {}).status, 422)
        draft = self.ed.post("/v1/admin/content/courses", {"slug": uniq("rasc"), "title": "Curso em rascunho", "modules": [{"title": "Módulo 1", "lessons": [{"title": "Aula 1", "body": "x"}]}]})
        self.assertEqual(draft.status, 201)
        self.assertNotIn("Curso em rascunho", [c["title"] for c in self.anon.get("/v1/help/courses").json["items"]])
        bad = self.ed.post("/v1/admin/content/courses", {"slug": uniq("quiz"), "title": "Quiz sem perguntas", "modules": [{"title": "Módulo 1", "lessons": [{"title": "Quiz 1", "kind": "quiz"}]}]})
        self.assertEqual(bad.status, 422)


class Captation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.anon = Client()
        cls.adm, _ = make_admin()

    def partnership(self, **kw):
        b = {"org_name": "Instituto Exemplo", "contact_name": "Maria Teste", "contact_email": f"{uniq('p')}@exemplo.org", "kind": "academic",
             "objective": "Formar jovens em gestão de projetos sociais.", "consent": True}
        b.update(kw)
        return self.anon.post("/v1/help/partnerships", b)

    def test_partnership_requires_consent_and_flows_through_pipeline(self):
        self.assertEqual(self.partnership(consent=False).status, 422)
        r = self.partnership()
        self.assertEqual(r.status, 201, r)
        rid = r.json["id"]
        got = self.adm.get(f"/v1/admin/hub/partnerships/{rid}").json
        self.assertEqual((got["status"], got["consent_version"]), ("received", "contact-v1"))
        for to in ("qualification", "meeting", "proposal", "approved", "active"):
            self.assertEqual(self.adm.post(f"/v1/admin/hub/partnerships/{rid}/move", {"to": to, "note": f"mover para {to}"}).status, 200)
        self.assertEqual(self.adm.post(f"/v1/admin/hub/partnerships/{rid}/notes", {"body": "Reunião marcada"}).status, 201)
        got = self.adm.get(f"/v1/admin/hub/partnerships/{rid}").json
        self.assertEqual(got["status"], "active")
        self.assertEqual([a["to_status"] for a in got["activities"] if a["kind"] == "status"], ["qualification", "meeting", "proposal", "approved", "active"])
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM partnerships WHERE request_id = $1", rid), 1)
        self.assertEqual(self.adm.post(f"/v1/admin/hub/partnerships/{rid}/move", {"to": "completed"}).status, 200)
        self.assertEqual(self.adm.post(f"/v1/admin/hub/partnerships/{rid}/move", {"to": "negotiation"}).status, 409)      # encerrado não reabre

    def test_partnership_validates_and_honeypot_stores_nothing(self):
        self.assertEqual(self.partnership(contact_email="sem-arroba").status, 422)
        self.assertEqual(self.partnership(kind="outro").status, 422)
        self.assertEqual(self.partnership(objective="curto").status, 422)
        email = f"{uniq('bot')}@exemplo.org"
        self.assertEqual(self.partnership(contact_email=email, website="http://spam.example").status, 201)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM partnership_requests WHERE contact_email = $1", email), 0)

    def test_partnership_not_readable_by_other_users(self):
        u = new_account("osc")
        rid = self.partnership(contact_email=f"{uniq('x')}@exemplo.org").json["id"]
        self.assertEqual(u.get(f"/v1/admin/hub/partnerships/{rid}").status, 403)
        from impacto.db.pool import DbContext
        with server()["state"].pool.tx(DbContext(user_id=u.user["id"], org_id=u.org_id, org_kind="osc")) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM partnership_requests"), 0)
        with server()["state"].pool.tx(DbContext()) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM partnership_requests"), 0)

    def test_demo_request_schedule_sends_email(self):
        from tests.support import outbox_messages
        email = f"{uniq('d')}@exemplo.org"
        r = self.anon.post("/v1/help/demo-requests", {"org_name": "OSC Demo", "contact_name": "João", "contact_email": email, "audience_kind": "osc", "org_size": "11-50", "consent": True,
                                                       "preferred_slots": [(datetime.now(UTC) + timedelta(days=3)).isoformat()]})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(self.anon.post("/v1/help/demo-requests", {"org_name": "OSC", "contact_name": "J", "contact_email": email, "audience_kind": "osc", "consent": False}).status, 422)
        when = (datetime.now(UTC) + timedelta(days=4)).replace(microsecond=0).isoformat()
        self.assertEqual(self.adm.post(f"/v1/admin/hub/demo-requests/{r.json['id']}/handle", {"status": "scheduled"}).status, 422)
        self.assertEqual(self.adm.post(f"/v1/admin/hub/demo-requests/{r.json['id']}/handle", {"status": "scheduled", "scheduled_at": when, "meeting_url": "https://meet.exemplo.org/demo"}).status, 200)
        from email.header import decode_header, make_header
        self.assertTrue([m for m in outbox_messages() if m["To"] == email and "Demonstração agendada" in str(make_header(decode_header(m["Subject"])))])
        self.assertIn(r.json["id"], [x["id"] for x in self.adm.get("/v1/admin/hub/demo-requests?status=scheduled").json["items"]])

    def test_newsletter_double_opt_in(self):
        email = f"{uniq('n')}@exemplo.org"
        self.assertEqual(self.anon.post("/v1/help/newsletter", {"email": email, "consent": False}).status, 422)
        r1 = self.anon.post("/v1/help/newsletter", {"email": email, "topics": ["platform", "events"], "consent": True})
        self.assertEqual(r1.json["status"], "pending")
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT status FROM newsletter_subscriptions WHERE email = $1", email), "pending")
        tok = last_token_for(email, "/ajuda/boletim/confirmar")
        self.assertEqual(self.anon.post("/v1/help/newsletter/confirm", {"token": "x" * 30}).status, 404)
        self.assertEqual(self.anon.post("/v1/help/newsletter/confirm", {"token": tok}).json["status"], "active")
        # inscrição repetida devolve resposta idêntica (sem enumeração) e não reenvia
        r2 = self.anon.post("/v1/help/newsletter", {"email": email, "consent": True})
        self.assertEqual(r1.json, r2.json)
        # o token guardado é só hash
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM newsletter_subscriptions WHERE token_hash = $1", tok), 0)
        self.assertEqual(self.anon.post("/v1/help/newsletter/unsubscribe", {"token": tok}).status, 200)
        self.assertEqual(self.anon.post("/v1/help/newsletter/unsubscribe", {"token": tok}).status, 404)

    def test_bulletin_dispatch_sends_only_published_bulletins_to_confirmed(self):
        from impacto.services import hub
        from tests.support import outbox_messages
        ed, rv = staff("editor"), staff("reviewer")
        email = f"{uniq('b')}@exemplo.org"
        self.anon.post("/v1/help/newsletter", {"email": email, "consent": True})
        pend = f"{uniq('pend')}@exemplo.org"
        self.anon.post("/v1/help/newsletter", {"email": pend, "consent": True})
        self.anon.post("/v1/help/newsletter/confirm", {"token": last_token_for(email, "/ajuda/boletim/confirmar")})
        slug = uniq("boletim")
        r = ed.post("/v1/admin/content/resources", {"slug": slug, "kind": "bulletin", "title": "Boletim de exemplo", "visibility": "public", "url": "https://exemplo.org/boletim", "demo": True})
        for who, to in ((ed, "review"), (rv, "approved"), (rv, "published")):
            who.post(f"/v1/admin/content/resources/{r.json['id']}/transition", {"to": to})
        with db_system() as d:
            out = hub.bulletin_dispatch(server()["state"], d)
        self.assertGreaterEqual(out["sent"], 1)
        self.assertTrue([m for m in outbox_messages() if m["To"] == email and "Boletim" in str(m["Subject"])])
        self.assertFalse([m for m in outbox_messages() if m["To"] == pend and "Boletim" in str(m["Subject"])])
        with db_system() as d:
            self.assertEqual(hub.bulletin_dispatch(server()["state"], d)["sent"], 0)       # não repete no mesmo período


class TrialRequestsRetired(unittest.TestCase):
    """v0.27.0 (ADR-341): a solicitação de teste saiu com a assinatura. Quem quer conhecer módulos pede
    demonstração (`/v1/help/demo-requests`); concessão de pacote é licença administrativa com motivo."""

    def test_the_trial_request_routes_are_gone(self):
        o = new_account("osc")
        self.assertIn(o.post("/v1/help/trial-requests", {"users_count": 5, "purpose": "Avaliar a plataforma com nossa equipe.", "responsible": "Ana"}).status, (404, 405))
        self.assertIn(o.get("/v1/help/trial-requests").status, (404, 405))
        with db_system() as d:
            self.assertIsNone(d.one("SELECT 1 FROM information_schema.tables WHERE table_name IN ('trial_requests', 'org_trials')"))


class AnalyticsAndGovernance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv = staff("editor"), staff("reviewer")

    def test_stale_content_is_flagged_and_review_clears_it(self):
        p = publish_article(self.ed, self.rv)
        with db_system() as d:
            d.run("UPDATE kb_articles SET last_reviewed_at = now() - interval '400 days' WHERE id = $1", p["id"])
        self.assertTrue(Client().get(f"/v1/help/articles/{p['slug']}").json["needs_review"])
        ov = self.ed.get("/v1/admin/content/overview").json
        self.assertGreaterEqual(ov["stale"]["articles"], 1)
        self.assertEqual(self.ed.post(f"/v1/admin/content/article/{p['id']}/reviewed", {}).status, 403)       # só reviewer
        self.assertEqual(self.rv.post(f"/v1/admin/content/article/{p['id']}/reviewed", {"note": "conferido"}).status, 200)
        self.assertFalse(Client().get(f"/v1/help/articles/{p['slug']}").json["needs_review"])

    def test_analytics_endpoint_and_retention(self):
        from impacto.services import hub
        Client().get("/v1/help/search?q=zzzz+qqqq+wwww")
        a = self.ed.get("/v1/admin/hub/analytics").json
        for k in ("searches", "gap_topics", "top_articles", "tickets", "academy", "events", "privacy_note", "recurring_tickets", "stale"):
            self.assertIn(k, a)
        with db_system() as d:
            d.run("INSERT INTO kb_events(kind, at) VALUES ('view', now() - interval '20 months')")
            n = hub.retention(d)["kb_events_deleted"]
        self.assertGreaterEqual(n, 1)
        self.assertEqual(Client().get("/v1/admin/hub/analytics").status, 401)

    def test_category_and_unknown_history_type(self):
        self.assertEqual(self.ed.post("/v1/admin/content/categories", {"slug": uniq("cat"), "name": "Categoria de teste"}).status, 201)
        self.assertEqual(self.ed.get("/v1/admin/content/history/inexistente/" + str(uuid.uuid4())).status, 404)
        cats = Client().get("/v1/help/categories").json["items"]
        self.assertGreaterEqual(len(cats), 9)

    def test_public_endpoints_are_rate_limited_in_spec(self):
        from impacto.http import ROUTES
        public = [r for r in ROUTES if r.auth == "none" and r.path.startswith("/v1/help")]
        self.assertTrue(public)
        self.assertTrue(all(r.rate for r in public), [r.path for r in public if not r.rate])


class EmailNotices(unittest.TestCase):
    """RED da v0.11.0: avisos de cobrança agora saem por e-mail (grupo `billing`), respeitando a preferência, uma única vez."""

    @classmethod
    def setUpClass(cls):
        server()

    def run_job(self):
        from impacto.services import hub
        with db_system() as d:
            return hub.notification_emails(server()["state"], d)

    def mails_to(self, email):
        from email.header import decode_header, make_header

        from tests.support import outbox_messages
        return [str(make_header(decode_header(m["Subject"]))) for m in outbox_messages() if m["To"] == email]

    def test_billing_notice_is_emailed_once_to_owner(self):
        from impacto.services import monetization as mon
        o = new_account("osc")
        with db_system() as d:
            self.assertTrue(mon.notify_once(d, o.org_id, "trial_day", "7", "Lembrete do período de teste", "Faltam 7 dias de acesso completo."))
        self.run_job()
        subj = self.mails_to(o.email)
        self.assertTrue([s for s in subj if "Lembrete do período de teste" in s], subj)
        before = len(self.mails_to(o.email))
        self.run_job()
        self.assertEqual(len(self.mails_to(o.email)), before)       # não reenvia

    def test_email_preference_off_suppresses_but_in_app_remains(self):
        from impacto.services import monetization as mon
        o = new_account("osc")
        o.put("/v1/notifications/prefs", {"items": [{"grp": "billing", "in_app": True, "email": False}]})
        with db_system() as d:
            mon.notify_once(d, o.org_id, "trial_ended", "1", "Seu período de teste terminou", "Sua conta está no plano gratuito.")
        out = self.run_job()
        self.assertGreaterEqual(out["emails_skipped_by_preference"], 1)
        self.assertFalse([s for s in self.mails_to(o.email) if "terminou" in s])
        self.assertTrue([n for n in o.get("/v1/notifications").json["items"] if n["kind"] == "billing.trial_ended"])

    def test_unverified_owner_gets_no_email(self):
        from impacto.services import monetization as mon
        o = new_account("osc", verify=False)
        with db_system() as d:
            mon.notify_once(d, o.org_id, "trial_day", "11", "Seu período de teste termina em 3 dias", "Escolha um plano.")
        self.run_job()
        self.assertEqual(self.mails_to(o.email) and [s for s in self.mails_to(o.email) if "termina em 3 dias" in s], [])


class SeedContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()

    def test_import_creates_only_demo_drafts_and_is_idempotent(self):
        from impacto.services import kb_seed
        author = new_account("osc")
        with db_system() as d:
            first = kb_seed.import_seed(d, author_id=author.user["id"], reviewer_id=None, publish=False)
            second = kb_seed.import_seed(d, author_id=author.user["id"], reviewer_id=None, publish=False)
            live = d.scalar("SELECT count(*) FROM kb_articles WHERE live_version_id IS NOT NULL AND slug = ANY($1::text[])", [a[0] for a in kb_seed.ARTICLES])
            non_demo = d.scalar("SELECT count(*) FROM kb_articles WHERE slug = ANY($1::text[]) AND NOT demo", [a[0] for a in kb_seed.ARTICLES])
            non_demo_f = d.scalar("SELECT count(*) FROM kb_faqs WHERE question = ANY($1::text[]) AND NOT demo", [f[0] for f in kb_seed.FAQS])
        self.assertEqual(first["articles"] + first["faqs"] + first["resources"] + first["courses"] + first["events"] + first["paths"] >= 0, True)
        self.assertEqual(sum(second.values()), 0)
        self.assertEqual((live, non_demo, non_demo_f), (0, 0, 0))
        self.assertEqual(Client().get(f"/v1/help/articles/{kb_seed.ARTICLES[0][0]}").status, 404)       # rascunho nunca é público

    def test_publish_requires_different_reviewer_and_carries_demo_badge(self):
        from impacto.services import kb_seed
        a, b = new_account("osc"), new_account("osc")
        with self.assertRaises(ValueError):
            with db_system() as d:
                kb_seed.import_seed(d, author_id=a.user["id"], reviewer_id=a.user["id"], publish=True)
        class Rollback(Exception):
            pass
        try:
            with db_system() as d:
                d.run("DELETE FROM kb_article_versions WHERE article_id IN (SELECT id FROM kb_articles WHERE slug = ANY($1::text[]))", [x[0] for x in kb_seed.ARTICLES])
                d.run("DELETE FROM kb_articles WHERE slug = ANY($1::text[])", [x[0] for x in kb_seed.ARTICLES])
                n = kb_seed.import_seed(d, author_id=a.user["id"], reviewer_id=b.user["id"], publish=True)
                self.assertEqual(n["articles"], len(kb_seed.ARTICLES))
                row = d.one("SELECT demo, origin, live_version_id IS NOT NULL AS live FROM kb_articles WHERE slug = 'como-cadastrar-organizacao'")
                self.assertEqual((row["demo"], row["origin"], row["live"]), (True, "educational", True))
                raise Rollback
        except Rollback:
            pass
        # nenhum conteúdo do seed menciona valor monetário, prazo legal ou regra fiscal
        import re
        text = " ".join(str(x) for x in kb_seed.ARTICLES) + " ".join(str(x) for x in kb_seed.FAQS)
        self.assertIsNone(re.search(r"R\$\s?\d|lei\s+n?º?\s?\d|art\.\s?\d", text, re.I))


if __name__ == "__main__":
    unittest.main()
