"""E2E (Chromium/Playwright) do dossiê longitudinal v0.30.0: a OSC dona e o financiador abrem a MESMA leitura, com origem,
atualidade e lacunas visíveis; a página passa na verificação de acessibilidade e contraste (claro e escuro); sem erro de console."""
import re
import unittest

from tests.support import PASSWORD, ROOT, server
from tests.test_e2e_knowledge import CONTRAST_JS
from tests.test_e2e_v080 import A11Y_JS
from tests.test_v080 import funded_pair

DIST = ROOT / "web" / "dist" / "index.html"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class DossierE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base = st["base"]
        cls.state = st["state"]
        cls._old = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base
        cls.pair = funded_pair()
        cls.pair["osc"].post(f"/v1/projects/{cls.pair['pid']}/evidences", {"kind": "report", "title": "Relatório E2E", "method": "document"})
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old

    def page(self, dark=False):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="dark" if dark else "light")
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

    def _open(self, p):
        p.goto(f"{self.base}/projetos/{self.pair['pid']}/dossie")
        p.get_by_role("heading", name=re.compile("Dossiê do projeto")).wait_for()
        p.get_by_text("O que este dossiê é — e o que não é").wait_for()   # o dado chegou (na suíte completa o servidor está carregado: achado da 1ª regressão)
        txt = p.locator("main").inner_text()
        for needle in ("não é nota nem ranking", "Lacunas declaradas", "Origem:", "Evidências", "reportado × validado", "Declaradas (enviadas, aguardando)"):
            self.assertIn(needle, txt)
        return txt

    def test_owner_and_funder_open_the_same_dossier_with_sources_and_gaps(self):
        p = self.page()
        self.login(p, self.pair["osc"])
        a = self._open(p)
        self.assertEqual(p.evaluate(A11Y_JS), [])
        self.assertEqual(p.evaluate(CONTRAST_JS), [])
        self.assertEqual(p.errors, [])
        q = self.page(dark=True)
        self.login(q, self.pair["fu"])
        b = self._open(q)
        self.assertEqual(q.evaluate(CONTRAST_JS), [])
        self.assertEqual(q.errors, [])
        # os números são os mesmos para os dois lados (sem assimetria)
        for needle in ("Declaradas (enviadas, aguardando)\n1", "Com método de coleta declarado\n1 de 1"):
            self.assertIn(needle, a)
            self.assertIn(needle, b)
