"""E2E (Chromium/Playwright) da ajuda contextual v0.29.0: tooltip, popover, termo de glossário e página /ajuda/glossario.

Prova no navegador real, contra a SPA compilada: hover mostra a dica curta; foco por teclado mostra a dica; Enter abre o cartão
(role=dialog, título, fontes); Escape fecha e devolve o foco; clique fora fecha; toque (viewport móvel) abre; tema escuro e
`prefers-reduced-motion` não quebram nada; sem erro de console; verificação de acessibilidade e contraste da página do glossário.
Pulado se Playwright ou o build do frontend não existirem (o CI tem os dois)."""
import re
import unittest

from tests.support import PASSWORD, ROOT, new_account, server
from tests.test_e2e_knowledge import CONTRAST_JS
from tests.test_e2e_v080 import A11Y_JS

DIST = ROOT / "web" / "dist" / "index.html"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class ContextualHelpE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base = st["base"]
        cls.state = st["state"]
        cls._old = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old

    def page(self, mobile=False, dark=False, reduced=False):
        ctx = self.browser.new_context(viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 900},
                                       has_touch=mobile, color_scheme="dark" if dark else "light", reduced_motion="reduce" if reduced else "no-preference")
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

    # ---------------------------------------------------------------------------------------- glossário público
    def test_glossary_page_lists_terms_filters_and_passes_a11y_and_contrast(self):
        p = self.page()
        p.goto(self.base + "/ajuda/glossario")
        p.get_by_role("heading", name="Glossário de conceitos").wait_for()
        self.assertGreaterEqual(p.locator("article.gloss-item").count(), 30)
        # cada termo tem fontes e "Como o IMPACTO usa"
        first = p.locator("article.gloss-item").first
        self.assertIn("Como o IMPACTO usa", first.inner_text())
        self.assertIn("Fontes", first.inner_text())
        # filtro por texto sem acento
        p.get_by_label("Procurar termo").fill("custodial")
        self.assertEqual(p.locator("article.gloss-item").count(), 1)
        self.assertIn("Não custodial", p.locator("article.gloss-item").first.inner_text())
        # filtro por área
        p.get_by_label("Procurar termo").fill("")
        p.get_by_label("Área").select_option("economia")
        self.assertGreaterEqual(p.locator("article.gloss-item").count(), 3)
        self.assertTrue(all("Modelo econômico" in t for t in p.locator("article.gloss-item h2").all_inner_texts()))
        # âncora: /ajuda/glossario#lgpd foca o termo
        p.goto(self.base + "/ajuda/glossario#lgpd")
        p.get_by_role("heading", name="Glossário de conceitos").wait_for()
        p.wait_for_function("() => document.activeElement && document.activeElement.id === 'c-lgpd'")
        self.assertEqual(p.evaluate(A11Y_JS), [])
        self.assertEqual(p.evaluate(CONTRAST_JS), [])
        self.assertEqual(p.errors, [])

    def test_glossary_page_in_dark_theme_has_no_contrast_failures(self):
        p = self.page(dark=True)
        p.goto(self.base + "/ajuda/glossario")
        p.get_by_role("heading", name="Glossário de conceitos").wait_for()
        self.assertEqual(p.evaluate(CONTRAST_JS), [])
        self.assertEqual(p.errors, [])

    # ---------------------------------------------------------------------------------------- termo em página real
    def test_term_on_opportunities_page_mouse_keyboard_escape_and_outside_click(self):
        acct = new_account("osc")
        p = self.page()
        self.login(p, acct)
        p.goto(self.base + "/oportunidades")
        p.get_by_role("heading", name="Oportunidades").wait_for()
        trigger = p.locator('[data-concept="match"] [role=button]').first
        tip = p.locator('[data-concept="match"] [role="tooltip"]').first
        # hover → dica curta visível (texto vem do catálogo)
        trigger.hover()
        tip.wait_for(state="visible")            # a dica só existe no DOM enquanto visível (nome acessível do título fica limpo)
        self.assertIn("critério a critério", tip.inner_text())
        p.mouse.move(5, 5)
        tip.wait_for(state="detached")
        # foco por teclado → dica visível
        trigger.focus()
        tip.wait_for(state="visible")
        self.assertEqual(trigger.get_attribute("aria-expanded"), "false")
        # Enter → cartão (dialog) com título, "Como o IMPACTO usa", fontes
        p.keyboard.press("Enter")
        dlg = p.get_by_role("dialog", name="Compatibilidade (match)")
        dlg.wait_for()
        self.assertEqual(trigger.get_attribute("aria-expanded"), "true")
        txt = dlg.inner_text()
        for needle in ("Por que importa", "Como o IMPACTO usa", "Limites", "Fontes", "não é aprovação"):
            self.assertIn(needle, txt)
        # "veja também" navega dentro do cartão sem fechar
        dlg.get_by_role("button", name="Compatibilidade territorial").click()
        p.get_by_role("dialog", name="Compatibilidade territorial").wait_for()
        self.assertIn("código IBGE", p.get_by_role("dialog").inner_text())
        # Escape fecha e devolve o foco ao gatilho
        p.keyboard.press("Escape")
        p.wait_for_function("() => !document.querySelector('[role=dialog].pop')")
        self.assertTrue(p.evaluate("() => document.activeElement && document.activeElement.className.includes('pop-trigger')"))
        # clique abre de novo; clique fora fecha
        trigger.click()
        p.get_by_role("dialog", name="Compatibilidade (match)").wait_for()
        p.mouse.click(10, 10)
        p.wait_for_function("() => !document.querySelector('[role=dialog].pop')")
        self.assertEqual(p.errors, [])

    def test_a_heading_made_of_terms_keeps_a_clean_accessible_name(self):
        """Achado da regressão: <button> dentro de <h2> virava "Originalidade , similaridade" no nome acessível. O termo é role=button inline."""
        acct = new_account("osc")
        p = self.page()
        self.login(p, acct)
        p.goto(self.base + "/ia")
        p.get_by_role("heading", name="Central de IA").wait_for()
        p.goto(self.base + "/oportunidades")
        p.get_by_role("heading", name="Oportunidades").wait_for()
        snap = p.locator("article, main").first.aria_snapshot()
        self.assertNotIn(" , ", snap)
        self.assertIn('button "compatibilidade"', snap)
        self.assertEqual(p.errors, [])

    def test_term_on_touch_device_opens_card_and_card_fits_viewport(self):
        acct = new_account("osc")
        p = self.page(mobile=True)
        self.login(p, acct)
        p.goto(self.base + "/oportunidades")
        p.get_by_role("heading", name="Oportunidades").wait_for()
        p.locator('[data-concept="edital"] [role=button]').first.tap()
        dlg = p.get_by_role("dialog", name="Edital / chamada")
        dlg.wait_for()
        box = dlg.bounding_box()
        self.assertGreaterEqual(box["x"], 0)
        self.assertLessEqual(box["x"] + box["width"], 390)
        self.assertLessEqual(box["y"] + box["height"], 844)
        dlg.get_by_role("button", name="Fechar").tap()
        p.wait_for_function("() => !document.querySelector('[role=dialog].pop')")
        self.assertEqual(p.errors, [])

    def test_info_icon_dark_and_reduced_motion_on_readiness_page(self):
        acct = new_account("osc")
        p = self.page(dark=True, reduced=True)
        self.login(p, acct)
        p.goto(self.base + "/prontidao")
        p.get_by_role("heading", name=re.compile("Prontidão da organização")).wait_for()
        btn = p.locator('[data-concept="diagnostico_prontidao"] button').first
        self.assertEqual(btn.get_attribute("aria-label"), "O que é Diagnóstico de prontidão")
        btn.click()
        dlg = p.get_by_role("dialog", name="Diagnóstico de prontidão")
        dlg.wait_for()
        self.assertIn("não selo nem certificação", dlg.inner_text())
        self.assertEqual(p.evaluate("el => getComputedStyle(el).animationName", dlg.element_handle()), "none")   # movimento reduzido
        self.assertEqual(p.evaluate(CONTRAST_JS), [])
        self.assertEqual(p.errors, [])

    def test_every_concept_used_on_pages_exists_in_the_catalog(self):
        """Um `GlossaryTerm id` ou `ContextualHelp id` sem conceito renderiza só o texto — e o teste acusa o id órfão no código."""
        import json
        cat = json.loads((ROOT / "config" / "concepts.json").read_text(encoding="utf-8"))["terms"]
        used = set()
        for f in (ROOT / "web" / "src" / "pages").glob("*.tsx"):
            used |= set(re.findall(r'(?:GlossaryTerm|ContextualHelp) id="([a-z0-9_]+)"', f.read_text(encoding="utf-8")))
        self.assertGreaterEqual(len(used), 12, used)
        self.assertEqual(used - set(cat), set(), "ids usados nas telas sem conceito no catálogo")
