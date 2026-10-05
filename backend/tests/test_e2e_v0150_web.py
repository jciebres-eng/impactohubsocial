"""Robustez FUNCIONAL da interface nas telas novas da v0.15.0 (sem camada de design).

Confere o que uma pessoa real encontra: a página abre, tem um único <h1>, não solta erro no console, o caminho
crítico funciona pelo navegador e — o ponto principal — a interface NÃO ESCONDE o que impede continuar.
Pulado quando Playwright ou o build do frontend não estão disponíveis.
"""
import re
import unittest

from tests.support import PASSWORD, ROOT, grant_premium, new_account, server

DIST = ROOT / "web" / "dist" / "index.html"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False

PAGES = ("/ideias", "/prontidao", "/documentos/montagens", "/documentos/modelos", "/assinatura/provedores",
         "/assinatura/politica")


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class CoreWebE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        # o servidor confere a origem do pedido do navegador: sem isto o login responde "Origem não permitida"
        cls._old_base = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.osc = new_account("osc", compliance="approved")
        grant_premium(cls.osc)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old_base

    def page(self):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        p = ctx.new_page()
        p.errors = []
        p.on("pageerror", lambda e: p.errors.append(str(e)))
        p.on("console", lambda m: p.errors.append(m.text)
             if m.type == "error" and "401" not in m.text and "404" not in m.text else None)
        return p

    def login(self, p, acct):
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(acct.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()

    def test_new_pages_open_clean(self):
        p = self.page()
        self.login(p, self.osc)
        for path in PAGES:
            p.goto(self.base + path)
            p.wait_for_timeout(300)
            h1 = p.locator("h1").count()
            self.assertEqual(h1, 1, f"{path}: esperado 1 <h1>, achei {h1}")
            dup = p.evaluate("""() => { const seen = {}, bad = [];
              document.querySelectorAll('[id]').forEach(e => { if (seen[e.id]) bad.push(e.id); seen[e.id] = 1; });
              return bad; }""")
            self.assertEqual(dup, [], f"{path}: IDs duplicados {dup}")
            self.assertEqual(p.evaluate("document.documentElement.lang"), "pt-BR", path)
        self.assertEqual(p.errors, [])

    def test_idea_becomes_project_through_the_interface(self):
        p = self.page()
        self.login(p, self.osc)
        p.goto(self.base + "/ideias")
        p.get_by_role("button", name="Anotar ideia").click()
        p.get_by_label("Título").fill("Cozinha comunitária do bairro")
        p.get_by_label(re.compile(r"^Problema")).fill("Famílias sem refeição regular no fim do mês.")
        p.get_by_role("button", name="Anotar", exact=True).click()
        p.get_by_text("Cozinha comunitária do bairro").first.wait_for()
        p.get_by_role("button", name="Transformar em projeto").first.click()
        p.get_by_role("button", name="Criar projeto").click()
        p.wait_for_url(re.compile(r"/projetos/[0-9a-f-]{36}"), timeout=10000)
        # a ideia continua lá, marcada como promovida
        p.goto(self.base + "/ideias")
        p.get_by_text("Virou projeto").first.wait_for()
        self.assertEqual(p.errors, [])

    def test_blocked_assembly_shows_what_is_missing_instead_of_generating(self):
        """Invariante de design: a interface NÃO pode esconder o que impede gerar o documento."""
        p = self.page()
        self.login(p, self.osc)
        pid = self.osc.post("/v1/projects", {"title": "Projeto para montar pela interface",
                                             "summary": "Resumo", "problem": "Problema.", "territory": "BR-MT",
                                             "causes": ["educacao"], "beneficiaries_count": 30,
                                             "budget_total_cents": 1_000_000}).json["id"]
        self.assertTrue(pid)
        p.goto(self.base + "/documentos/montagens")
        p.get_by_role("button", name="Nova montagem").click()
        tid = next(t["id"] for t in self.osc.get("/v1/document-templates?status=published").json["items"]
                   if t["code"] == "plano_monitoramento_base")
        p.get_by_label(re.compile(r"^Modelo")).select_option(value=tid)
        p.get_by_label("Título do documento").fill("Plano de monitoramento pela interface")
        p.get_by_label(re.compile(r"^Projeto")).select_option(label="Projeto para montar pela interface")
        p.get_by_role("button", name="Abrir montagem").click()
        p.wait_for_url(re.compile(r"/documentos/montagens/[0-9a-f-]{36}"), timeout=10000)
        p.get_by_text("Falta preencher").wait_for()
        # o botão de gerar existe, mas está desabilitado, com a razão à vista
        gen = p.get_by_role("button", name="Gerar documento")
        self.assertTrue(gen.is_disabled(), "a interface deixou gerar documento incompleto")
        p.get_by_text("O que impede gerar").wait_for()
        self.assertEqual(p.errors, [])

    def test_lifecycle_refusal_is_shown_to_the_person(self):
        p = self.page()
        self.login(p, self.osc)
        pid = self.osc.post("/v1/projects", {"title": "Projeto do ciclo pela interface", "summary": "Resumo",
                                             "problem": "Problema.", "territory": "BR-MT", "causes": ["educacao"],
                                             "beneficiaries_count": 30, "budget_total_cents": 1_000_000}).json["id"]
        p.goto(f"{self.base}/projetos/{pid}/situacao")
        p.get_by_text("Rascunho").first.wait_for()
        # transição que exige motivo: o campo aparece e o botão só libera com o motivo escrito
        p.get_by_label("Nova situação").select_option("cancelled")
        p.get_by_label(re.compile(r"^Motivo")).wait_for()
        self.assertTrue(p.get_by_role("button", name="Registrar mudança").is_disabled())
        p.get_by_label(re.compile(r"^Motivo")).fill("A contraparte desistiu da parceria.")
        p.get_by_role("button", name="Registrar mudança").click()
        p.get_by_text("Cancelado").first.wait_for()
        self.assertEqual(p.errors, [])

    def test_readiness_shows_unknown_separately_from_gaps(self):
        """Invariante de design: 'não sei' não pode ser apresentado como 'está ruim'."""
        p = self.page()
        self.login(p, new_account("osc", compliance="approved"))
        p.goto(self.base + "/prontidao")
        p.get_by_role("heading", name="Prontidão da organização").wait_for()
        p.get_by_text(re.compile("Lacunas")).first.wait_for()
        p.get_by_text(re.compile("Desconhecido")).first.wait_for()
        body = p.inner_text("main")
        self.assertIn("Desconhecido não é", body)
        self.assertIn("decisão é humana", body)
        self.assertEqual(p.errors, [])

    def test_provider_page_states_what_is_not_available(self):
        """Invariante de design: a interface não pode chamar o Gov.br de ICP-Brasil nem esconder indisponibilidade."""
        p = self.page()
        self.login(p, self.osc)
        p.goto(self.base + "/assinatura/provedores")
        p.get_by_role("heading", name="Provedores de assinatura").wait_for()
        p.get_by_text("ICP-Brasil", exact=False).first.wait_for()
        body = p.inner_text("main")
        self.assertIn("unavailable", body)
        self.assertIn("ICP-Brasil", body)
        self.assertIn("não existe assinatura simulada", body)
        self.assertEqual(p.errors, [])
