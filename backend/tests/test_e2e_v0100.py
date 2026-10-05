"""E2E v0.10.0 no Chromium: camada institucional — página da instituição (OSC), cadastro com natureza jurídica, verificações PRÓPRIAS de acessibilidade (não substituem axe/leitor de tela)."""
import re
import unittest

from tests.support import PASSWORD, new_account, server
from tests.test_e2e_v080 import A11Y_JS
from tests.test_e2e_web import DIST, HAVE_PW

if HAVE_PW:
    from playwright.sync_api import sync_playwright


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class WebV0100(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        cls._old = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old

    def session(self, acct, viewport=(1280, 900)):
        ctx = self.browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
        p = ctx.new_page()
        p.errors = []
        p.on("pageerror", lambda e: p.errors.append(str(e)))
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(acct.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()
        return p

    def test_institution_page_states_and_a11y(self):
        osc = new_account("osc")
        p = self.session(osc)
        p.goto(self.base + "/instituicao")
        p.get_by_role("heading", name="Instituição").first.wait_for()
        body = p.inner_text("body")
        # nunca afirma regularidade nem pontuação sem dados
        self.assertNotIn("100/100", body)
        self.assertEqual(p.evaluate(A11Y_JS), [])
        self.assertEqual(p.errors, [])

    def test_institution_mobile(self):
        osc = new_account("osc")
        p = self.session(osc, viewport=(375, 740))
        p.goto(self.base + "/instituicao")
        p.get_by_role("heading", name="Instituição").first.wait_for()
        self.assertFalse(p.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"))

    def test_register_shows_legal_nature_for_osc(self):
        ctx = self.browser.new_context()
        p = ctx.new_page()
        p.goto(self.base + "/cadastro")
        p.get_by_label("Natureza jurídica").wait_for()
        opts = p.get_by_label("Natureza jurídica").inner_text()
        self.assertIn("Coletivo", opts)
        self.assertEqual(p.evaluate(A11Y_JS), [])
