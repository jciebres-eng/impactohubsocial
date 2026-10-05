"""E2E v0.9.0 no Chromium: Biblioteca de Soluções — busca por intenção, rótulos de verdade, perfil, comparador, adaptação, cadastro e fila administrativa,
com verificações PRÓPRIAS de acessibilidade (não substituem axe/leitor de tela, não executados neste ambiente) e em viewport móvel."""
import re
import unittest
import uuid

from tests.support import PASSWORD, db_system, make_admin, new_account, server
from tests.test_e2e_v080 import A11Y_JS
from tests.test_e2e_web import DIST, HAVE_PW
from tests.test_v090_solutions import mk

if HAVE_PW:
    from playwright.sync_api import sync_playwright


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class WebV090(unittest.TestCase):
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

    def session(self, acct, viewport=(1280, 900), heading="Olá"):
        ctx = self.browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
        p = ctx.new_page()
        p.errors = []
        p.on("pageerror", lambda e: p.errors.append(str(e)))
        p.on("console", lambda m: p.errors.append(m.text) if m.type == "error" and "401" not in m.text else None)
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(acct.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile(heading)).wait_for()
        return p

    def check(self, p, path, heading):
        p.goto(self.base + path)
        p.get_by_role("heading", name=re.compile(heading)).first.wait_for()
        issues = p.evaluate(A11Y_JS)
        self.assertEqual(issues, [], f"{path}: {issues}")

    def test_search_profile_compare_adapt_journey(self):
        osc = new_account("osc")
        tag = uuid.uuid4().hex[:5]
        s1 = mk(osc, title=f"Oficinas de arte no CAPS {tag}", summary="Oficinas de artes e música para usuários do Centro de Atenção Psicossocial.", themes=["saude", "cultura"],
                population=["saude_mental"], institutions=["caps"], ods=[3], uf="MT", license="cc_by", allow_adaptation=True, allow_replication=True, budget_cents=5000000)
        s2 = mk(osc, title=f"Arteterapia comunitária {tag}", summary="Grupos de arteterapia para pessoas em sofrimento psíquico, junto à rede de saúde mental.", themes=["saude"],
                population=["saude_mental"], ods=[3], uf="SP", budget_cents=2000000)
        fu = new_account("company")
        p = self.session(fu)
        self.check(p, "/solucoes", "Biblioteca de soluções")
        p.get_by_label("O que você procura?").fill("artes caps")
        p.get_by_role("button", name="Buscar").click()
        p.get_by_role("link", name=re.compile(f"Oficinas de arte no CAPS {tag}")).first.wait_for()
        p.get_by_text("Entendemos:").wait_for()
        # rótulo de verdade: autodeclarado nunca aparece como comprovado
        card = p.locator("article", has_text=f"Oficinas de arte no CAPS {tag}").first
        self.assertIn("AUTODECLARADO", card.inner_text()); self.assertNotIn("COMPROVADO", card.inner_text())
        self.assertIn("Por que apareceu", card.inner_text())
        # modos de visualização
        for view in ("Lista", "Por ODS", "Mapa", "Financiamento", "Pesquisa", "Cases", "Cartões"):
            p.get_by_role("tab", name=view).click()
        self.assertEqual(p.evaluate(A11Y_JS), [])
        # comparar
        p.get_by_role("tab", name="Cartões").click()
        p.get_by_label("Comparar").nth(0).check(); p.get_by_label("Comparar").nth(1).check()
        p.get_by_role("button", name="Comparar").click()
        p.get_by_role("heading", name="Comparar soluções").wait_for()
        p.get_by_role("table", name="Comparação de soluções").wait_for()
        self.assertEqual(p.evaluate(A11Y_JS), [])
        # perfil + adaptação
        p.goto(self.base + f"/solucoes/{s1}")
        p.get_by_role("heading", name=re.compile(f"Oficinas de arte no CAPS {tag}")).first.wait_for()
        self.assertIn("AUTODECLARADO", p.locator("main").inner_text())
        self.assertIn("sem dados", p.locator("main").inner_text())          # replicabilidade nunca inventada
        self.assertEqual(p.evaluate(A11Y_JS), [])
        p.get_by_role("button", name="Adaptar para meu território").click()
        p.get_by_role("button", name="Simular adaptação").click()
        p.get_by_text("Dados insuficientes para estimativa confiável.").wait_for()
        self.assertEqual(p.errors, [])

    def test_owner_flow_and_admin_queue(self):
        osc = new_account("osc")
        p = self.session(osc)
        self.check(p, "/solucoes/nova", "Cadastrar solução")
        p.get_by_label("Título").fill("Biblioteca móvel para comunidades ribeirinhas")
        p.get_by_label("Resumo").fill("Embarcação adaptada com acervo rotativo para comunidades ribeirinhas sem biblioteca.")
        p.get_by_role("button", name="Educação", exact=True).click()
        p.get_by_role("button", name="Criar rascunho").click()
        p.get_by_role("heading", name=re.compile("Biblioteca móvel")).first.wait_for()
        self.assertIn("Rascunho", p.locator("main").inner_text())
        p.get_by_role("link", name="Editar").click()
        p.get_by_role("heading", name="Editar solução").wait_for()
        self.check(p, "/solucoes/minhas", "Minha área na biblioteca")
        self.assertEqual(p.errors, [])
        adm, _ = make_admin(mfa=False)
        old = self.state.settings.require_mfa_for_admins
        self.state.settings.require_mfa_for_admins = False
        self.addCleanup(setattr, self.state.settings, "require_mfa_for_admins", old)
        with db_system() as d:
            plat = d.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1")
        pa = self.session(adm)
        pa.evaluate("""async (org) => { const c = document.cookie.split('; ').find(x => x.startsWith('impacto_csrf=')); const t = c ? decodeURIComponent(c.split('=')[1]) : '';
          const r = await fetch('/v1/me/switch-org', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': t}, body: JSON.stringify({org_id: org})}); return r.status; }""", plat)
        self.check(pa, "/admin/solucoes", "Soluções — verificação")
        self.assertEqual(pa.errors, [])

    def test_mobile_viewport_has_no_horizontal_scroll(self):
        fu = new_account("company")
        p = self.session(fu, viewport=(375, 740))
        for path, h in (("/solucoes", "Biblioteca de soluções"), ("/solucoes/preferencias", "Tese e personalização"), ("/solucoes/replicacao", "Marketplace de replicação")):
            self.check(p, path, h)
            self.assertLessEqual(p.evaluate("document.documentElement.scrollWidth"), 376, f"{path} rola na horizontal")
        self.assertEqual(p.errors, [])


if __name__ == "__main__":
    unittest.main()
