"""E2E no navegador (Chromium/Playwright) da Central de Conhecimento v0.12.0: 4 jornadas reais contra o servidor que serve a SPA compilada.
Conteúdo é publicado pela API com o fluxo de quatro olhos; pulado se Playwright ou o build não existirem."""
import re
import unittest
import uuid

from tests.support import PASSWORD, ROOT, Client, fresh_totp, new_account, server
from tests.test_e2e_v080 import A11Y_JS
from tests.test_v0120_knowledge import publish_article, staff, uniq

DIST = ROOT / "web" / "dist" / "index.html"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False


CONTRAST_JS = """() => {
  const bad = [], seen = new Set();
  const lum = (c) => { const [r,g,b] = c.map(v => { v/=255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); }); return 0.2126*r+0.7152*g+0.0722*b; };
  const parse = (s) => { const m = String(s).match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(',').map(parseFloat); return p.length >= 3 && (p[3] === undefined || p[3] > 0.5) ? p.slice(0,3) : null; };
  const bgOf = (el) => { let e = el; while (e) { const c = parse(getComputedStyle(e).backgroundColor); if (c) return c; e = e.parentElement; } return [255,255,255]; };
  document.querySelectorAll('p,span,a,button,li,td,th,h1,h2,h3,label,strong,dt,dd,summary').forEach(el => {
    if (!el.textContent || !el.textContent.trim() || el.children.length) return;
    const st = getComputedStyle(el), fg = parse(st.color); if (!fg) return;
    const bg = bgOf(el), l1 = lum(fg), l2 = lum(bg);
    const ratio = (Math.max(l1,l2)+0.05) / (Math.min(l1,l2)+0.05);
    const size = parseFloat(st.fontSize), bold = (parseInt(st.fontWeight)||400) >= 700;
    const need = (size >= 24 || (size >= 18.66 && bold)) ? 3.0 : 4.5;
    const key = st.color + '|' + bg.join(',') + '|' + Math.round(size);
    if (ratio < need && !seen.has(key)) { seen.add(key); bad.push(st.color + ' ' + Math.round(size) + 'px -> ' + (Math.round(ratio*100)/100) + ':1 (exige ' + need + ') em "' + el.textContent.trim().slice(0,24) + '"'); }
  });
  return bad;
}"""


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class KnowledgeE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base = st["base"]
        cls.state = st["state"]
        cls._old = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base
        cls.ed, cls.rv, cls.sup = staff("editor"), staff("reviewer"), staff("support")
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old

    def page(self, mobile=False):
        ctx = self.browser.new_context(viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 900})
        p = ctx.new_page()
        p.errors = []
        p.on("pageerror", lambda e: p.errors.append(str(e)))
        p.on("console", lambda m: p.errors.append(m.text) if m.type == "error" and "401" not in m.text and "404" not in m.text else None)
        return p

    def login(self, p, acct):
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(acct.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()

    # Jornada 1 — visitante: busca, lê o guia, o assistente recusa o que não sabe, pede demonstração (tudo sem login)
    def test_visitor_search_guide_assistant_and_demo(self):
        slug = uniq("prestacao")
        publish_article(self.ed, self.rv, slug=slug, title="Prestação de contas passo a passo E2E")
        p = self.page(mobile=True)
        p.goto(self.base + "/ajuda")
        p.get_by_role("heading", name="Como podemos ajudar?").wait_for()
        p.get_by_label("Buscar na Central de Conhecimento").fill("prestação de contas")
        p.get_by_role("button", name="Buscar", exact=True).click()
        p.get_by_role("link", name="Prestação de contas passo a passo E2E").first.click()
        p.get_by_role("heading", name="Prestação de contas passo a passo E2E").wait_for()
        p.get_by_text("Reúna os comprovantes").wait_for()
        p.get_by_text("Entre para salvar seu progresso").wait_for()
        # assistente: sem base → recusa honesta e ação de chamado
        p.goto(self.base + "/ajuda")
        p.get_by_label("Pergunte ao assistente").fill("qual a cotação do dólar hoje")
        p.get_by_role("button", name="Perguntar").click()
        p.get_by_text("Não encontrei informação suficiente na base oficial.").wait_for()
        # demonstração pública com consentimento
        p.goto(self.base + "/ajuda/demonstracao")
        p.get_by_role("textbox", name="Organização", exact=True).fill("Instituto E2E")
        p.get_by_label("Seu nome").fill("Ana E2E")
        p.get_by_label("E-mail").fill(f"ana-{uuid.uuid4().hex[:6]}@teste.org")
        btn = p.get_by_role("button", name="Pedir demonstração")
        self.assertTrue(btn.is_disabled())                       # sem consentimento não envia
        p.get_by_role("checkbox").check()
        btn.click()
        p.get_by_text("Pedido recebido").wait_for()
        self.assertEqual(p.errors, [])

    # Jornada 2 — OSC: lê o guia, marca checklist (persiste), avalia e abre chamado; a equipe responde e a OSC vê
    def test_osc_checklist_feedback_and_support_ticket(self):
        slug = uniq("checklist")
        publish_article(self.ed, self.rv, slug=slug, title="Guia com checklist E2E", visibility="authenticated")
        osc = new_account("osc")
        p = self.page()
        self.login(p, osc)
        p.goto(f"{self.base}/ajuda/{slug}")
        p.get_by_role("heading", name="Guia com checklist E2E").wait_for()
        p.get_by_label("Comprovantes reunidos").check()
        p.wait_for_timeout(400)
        p.reload()
        p.get_by_label("Comprovantes reunidos").wait_for()
        self.assertTrue(p.get_by_label("Comprovantes reunidos").is_checked())
        p.get_by_role("button", name="Ajudou", exact=True).click()
        p.get_by_text("Obrigado pelo retorno").wait_for()
        p.get_by_role("link", name="Ainda com dúvida? Abra um chamado").click()
        p.get_by_label("Resumo").fill("Não consigo anexar a evidência")
        p.get_by_label("Descreva o que aconteceu").fill("Ao anexar o comprovante o botão não responde.")
        p.get_by_role("button", name="Enviar chamado").click()
        p.get_by_role("heading", name=re.compile("Não consigo anexar")).wait_for()
        tid = p.url.rstrip("/").split("/")[-1]
        r = self.sup.post(f"/v1/admin/support/tickets/{tid}/messages", {"body": "Olá! Já estamos verificando."})
        self.assertEqual(r.status, 201, r)
        p.reload()
        p.get_by_text("Já estamos verificando.").wait_for()
        self.assertEqual(p.errors, [])

    # Jornada 3 — Academia: matrícula, aulas, quiz reprovado/aprovado, certificado e verificação pública
    def test_academy_course_quiz_and_certificate(self):
        slug = uniq("curso")
        body = {"slug": slug, "title": "Curso E2E de evidências", "summary": "Exemplo.", "hours": 1.0, "pass_score": 70, "cert_enabled": True, "demo": True, "visibility": "public",
                "modules": [{"title": "Módulo único", "lessons": [
                    {"title": "Leitura inicial", "kind": "text", "body": "Conteúdo da primeira aula."},
                    {"title": "Quiz final", "kind": "quiz", "quiz": [{"q": "Evidências devem ser enviadas?", "options": ["Não", "Sim"], "answer": 1}]}]}]}
        r = self.ed.post("/v1/admin/content/courses", body)
        self.assertEqual(r.status, 201, r)
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/courses/{r.json['id']}/transition", {"to": to}).status, 200)
        osc = new_account("osc")
        p = self.page()
        self.login(p, osc)
        p.goto(f"{self.base}/ajuda/academia/{slug}")
        p.get_by_role("heading", name="Curso E2E de evidências").wait_for()
        p.get_by_text("não é diploma", exact=False).wait_for()
        p.get_by_role("button", name="Começar curso").click()
        p.get_by_role("button", name="Começar", exact=True).click()
        p.get_by_text("Conteúdo da primeira aula.").wait_for()
        p.get_by_role("button", name="Concluir aula").click()
        p.get_by_role("button", name="Próxima aula").click()
        p.get_by_role("heading", name="Quiz final").wait_for()
        p.get_by_label("Não", exact=True).check()
        p.get_by_role("button", name="Enviar respostas").click()
        p.get_by_text(re.compile("Nota 0%")).wait_for()
        p.get_by_label("Sim", exact=True).check()
        p.get_by_role("button", name="Enviar respostas").click()
        p.get_by_text(re.compile("Aprovada: 100%")).wait_for()
        p.goto(f"{self.base}/ajuda/academia/{slug}")
        p.get_by_role("button", name="Emitir certificado").click()
        p.get_by_role("heading", name="Verificação de certificado").wait_for()
        p.get_by_text("Certificado válido").wait_for()
        code = p.url.rstrip("/").split("/")[-1]
        anon = self.page()                                          # verificação pública, sem login
        anon.goto(f"{self.base}/ajuda/certificado/{code}")
        anon.get_by_text("Certificado válido").wait_for()
        anon.get_by_text("Não é diploma", exact=False).wait_for()
        self.assertEqual(p.errors + anon.errors, [])

    # Jornada 4 — evento (inscrição e lista de espera) e solicitação de teste (nunca automática; decisão do administrador)
    def test_event_registration_and_trial_request(self):
        from datetime import UTC, datetime, timedelta
        slug = uniq("evento")
        r = self.ed.post("/v1/admin/content/events", {"slug": slug, "kind": "webinar", "title": "Webinar E2E", "description": "Conversa.", "starts_at": (datetime.now(UTC) + timedelta(days=4)).isoformat(),
                                                      "duration_min": 45, "capacity": 1, "demo": True})
        self.assertEqual(r.status, 201, r)
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/events/{r.json['id']}/transition", {"to": to}).status, 200)
        a, b = new_account("osc"), new_account("osc")
        pa = self.page()
        self.login(pa, a)
        pa.goto(f"{self.base}/ajuda/eventos/{slug}")
        pa.get_by_role("button", name="Inscrever-me").click()
        pa.get_by_text("Inscrição confirmada").first.wait_for()
        pb = self.page()
        self.login(pb, b)
        pb.goto(f"{self.base}/ajuda/eventos/{slug}")
        pb.get_by_role("button", name="Entrar na lista de espera").click()
        pb.get_by_text("Na lista de espera").wait_for()
        # v0.27.0 (ADR-341): o pedido de teste saiu com a assinatura; a rota antiga responde "não encontrada".
        pb.goto(self.base + "/ajuda/teste")
        pb.get_by_text("Página não encontrada").wait_for()
        self.assertEqual(Client().get(f"/v1/help/events/{slug}").json["demo_label"] is not None, True)
        self.assertEqual(pa.errors + pb.errors, [])

    # Jornada 5 — equipe editorial: editor cria o guia no CMS (com MFA real), não consegue aprovar o próprio; revisor publica; visitante lê
    def test_cms_editor_cannot_self_approve_and_reviewer_publishes(self):
        ed = new_account("osc")
        from tests.support import db_system
        with db_system() as d:
            d.run("INSERT INTO staff_roles(user_id, role) VALUES ($1,'editor') ON CONFLICT DO NOTHING", ed.user["id"])
        secret = ed.post("/v1/auth/mfa/setup").json["secret"]
        self.assertEqual(ed.post("/v1/auth/mfa/enable", {"code": fresh_totp(secret)}).status, 200)
        p = self.page()
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(ed.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_label("Código do aplicativo autenticador").fill(fresh_totp(secret))
        p.get_by_role("button", name="Confirmar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()
        p.get_by_role("link", name="Central (equipe)").click()
        p.get_by_role("heading", name="Central de Conhecimento").wait_for()
        slug = uniq("cms")
        p.goto(self.base + "/admin/central/artigos/novo")
        p.get_by_label("Endereço (slug)").fill(slug)
        p.get_by_label("Quem pode ver").select_option("public")
        p.get_by_role("textbox", name="Título", exact=True).fill("Guia criado no CMS E2E")
        p.get_by_role("textbox", name="Texto", exact=True).fill("Conteúdo do guia escrito pela equipe.")
        p.get_by_role("button", name="Criar rascunho").click()
        p.get_by_text("Estado:").wait_for()
        p.get_by_role("button", name="Enviar para revisão").click()
        p.get_by_text("Em revisão").first.wait_for()
        self.assertEqual(Client().get(f"/v1/help/articles/{slug}").status, 404)           # ainda não é público
        vid = self.rv.get(f"/v1/admin/content/articles/{slug}").json["versions"][0]["id"]
        self.assertEqual(self.rv.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "approved"}).status, 200)
        self.assertEqual(self.rv.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": "published"}).status, 200)
        anon = self.page()
        anon.goto(f"{self.base}/ajuda/{slug}")
        anon.get_by_role("heading", name="Guia criado no CMS E2E").wait_for()
        self.assertEqual(p.errors + anon.errors, [])

    def test_new_pages_pass_basic_accessibility_checks(self):
        p = self.page()
        for path in ("/ajuda", "/ajuda/faq", "/ajuda/academia", "/ajuda/eventos", "/ajuda/biblioteca", "/ajuda/parcerias", "/ajuda/demonstracao", "/ajuda/boletim"):
            p.goto(self.base + path)
            p.locator("main").wait_for()
            p.wait_for_load_state("networkidle")
            self.assertEqual(p.evaluate(A11Y_JS), [], path)
        self.assertEqual(p.errors, [])

    def test_text_contrast_meets_wcag_aa_on_public_pages(self):
        """Contraste de texto (WCAG AA 4.5:1 / 3:1 para texto grande) medido no navegador, em tema claro e escuro."""
        for scheme in ("light", "dark"):
            ctx = self.browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme=scheme)
            p = ctx.new_page()
            for path in ("/ajuda", "/ajuda/faq", "/ajuda/academia", "/ajuda/eventos", "/ajuda/biblioteca", "/ajuda/demonstracao", "/entrar"):
                p.goto(self.base + path)
                p.locator("main, .auth-main").first.wait_for()
                p.wait_for_load_state("networkidle")
                self.assertEqual(p.evaluate(CONTRAST_JS), [], f"{scheme} {path}")
            ctx.close()

    def test_no_duplicate_element_ids_and_no_heading_level_skips(self):
        p = self.page()
        audit = """() => {
          const ids = {}; document.querySelectorAll('[id]').forEach(e => ids[e.id] = (ids[e.id]||0)+1);
          const dup = Object.entries(ids).filter(([,n]) => n > 1).map(([k]) => k);
          let last = 0; const skips = [];
          document.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(h => { const l = Number(h.tagName[1]);
            if (last && l > last + 1) skips.push('h' + last + '->h' + l); last = l; });
          return {dup, skips, lang: document.documentElement.lang || null};
        }"""
        for path in ("/ajuda", "/ajuda/faq", "/ajuda/academia", "/ajuda/eventos", "/ajuda/biblioteca", "/ajuda/boletim"):
            p.goto(self.base + path)
            p.locator("main").wait_for()
            p.wait_for_load_state("networkidle")
            r = p.evaluate(audit)
            self.assertEqual(r["dup"], [], f"IDs duplicados em {path}")
            self.assertEqual(r["skips"], [], f"nível de cabeçalho saltado em {path}")
            self.assertEqual(r["lang"], "pt-BR", path)
        self.assertEqual(p.errors, [])

    def test_private_pages_redirect_visitor_to_login(self):
        p = self.page()
        p.goto(self.base + "/ajuda/suporte")
        p.wait_for_url(re.compile(r"/entrar\?proximo="))
        self.assertEqual(p.errors, [])


if __name__ == "__main__":
    unittest.main()
