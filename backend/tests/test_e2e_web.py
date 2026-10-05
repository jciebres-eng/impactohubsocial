"""E2E no navegador (Chromium via Playwright) contra o servidor real servindo a SPA compilada (web/dist).
Pulado automaticamente se o Playwright/Chromium ou o build do frontend não estiverem disponíveis."""
import re
import unittest
import uuid
from pathlib import Path

from tests.support import PASSWORD, ROOT, db_system, last_token_for, new_account, server

DIST = ROOT / "web" / "dist" / "index.html"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class WebE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base = st["base"]
        cls.state = st["state"]
        cls._old_base = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base   # Origin do navegador = servidor de teste
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old_base

    def page(self, mobile=False):
        ctx = self.browser.new_context(viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 900})
        p = ctx.new_page()
        p.errors = []
        p.on("pageerror", lambda e: p.errors.append(str(e)))
        p.on("console", lambda m: p.errors.append(m.text) if m.type == "error" and "401" not in m.text else None)
        return p

    def test_osc_signup_project_with_assist_and_publish(self):
        p = self.page()
        email = f"e2e-{uuid.uuid4().hex[:8]}@teste.org"
        p.goto(self.base + "/cadastro")
        p.get_by_label("Seu nome").fill("Maria E2E")
        p.get_by_label("E-mail").fill(email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_label("Razão social").fill("Associação E2E de Teste")
        from tests.support import next_cnpj
        p.get_by_label("CNPJ").fill(next_cnpj())
        p.get_by_role("checkbox").check()
        p.get_by_role("button", name="Criar conta").click()
        p.get_by_text("Confirme seu e-mail").wait_for()
        token = last_token_for(email, "/verificar-email")
        p.goto(f"{self.base}/verificar-email?token={token}")
        p.get_by_text("E-mail confirmado").wait_for()
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile("Olá, Maria")).wait_for()
        # Projeto a partir de texto livre, com assistência
        p.goto(self.base + "/projetos/novo")
        p.get_by_role("textbox").first.fill("Precisamos de 10 violões de R$ 500 cada para aulas de música para 40 crianças.")
        p.get_by_role("button", name="Estruturar com assistência").click()
        p.get_by_text("Itens de orçamento encontrados").wait_for()
        p.get_by_label("Território de execução").fill("BR-MT-5105259")
        p.get_by_role("button", name="Salvar projeto").click()
        p.get_by_role("tab", name="Orçamento e etapas").wait_for()
        p.get_by_role("tab", name="Orçamento e etapas").click()
        p.get_by_text("R$ 5.000,00").first.wait_for()
        p.get_by_role("button", name="Publicar para financiadores").click()
        p.get_by_text("Projeto publicado").wait_for()
        self.assertEqual(p.errors, [])

    def test_company_feed_and_mobile_navigation(self):
        osc = new_account("osc")
        pid = osc.post("/v1/projects", {"title": "Projeto Visível E2E", "summary": "Resumo", "territory": "BR-MT", "causes": ["educacao"],
                                        "beneficiaries_count": 12, "budget_total_cents": 400000}).json["id"]
        osc.post(f"/v1/projects/{pid}/publish")
        co = new_account("company")
        p = self.page(mobile=True)
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(co.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()
        p.get_by_role("button", name="Menu").click()
        p.get_by_role("link", name="Projetos para apoiar").click()
        p.get_by_role("link", name="Projeto Visível E2E").click()
        p.get_by_role("button", name="Manifestar interesse").click()
        p.get_by_text("Interesse do financiador").first.wait_for()
        self.assertEqual(p.errors, [])

    def test_security_headers_on_spa(self):
        p = self.page()
        resp = p.goto(self.base + "/")
        h = resp.headers
        self.assertIn("default-src 'self'", h["content-security-policy"])
        self.assertEqual(h["x-frame-options"], "DENY")
        self.assertEqual(p.errors, [])  # nenhuma violação de CSP


if __name__ == "__main__":
    unittest.main()
