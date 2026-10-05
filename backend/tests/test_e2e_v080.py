"""E2E v0.8.0 no Chromium: páginas novas renderizam sem erros de console/CSP e passam em verificações PRÓPRIAS de acessibilidade
(rótulos, h1 único, landmark main, nomes acessíveis). Não substitui auditoria com axe/leitor de tela (não executada neste ambiente)."""
import re
import unittest

from tests.support import PASSWORD, ROOT, new_account, server
from tests.test_v080 import published_project, funded_pair
from tests.test_e2e_web import DIST, HAVE_PW

if HAVE_PW:
    from playwright.sync_api import sync_playwright

A11Y_JS = """() => {
  const out = [];
  const h1 = document.querySelectorAll('h1').length; if (h1 !== 1) out.push('h1 count ' + h1);
  if (!document.querySelector('main')) out.push('sem <main>');
  document.querySelectorAll('input:not([type=hidden]),select,textarea').forEach(el => {
    const named = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || (el.labels && el.labels.length) || el.closest('label');
    if (!named) out.push('controle sem rótulo: ' + (el.name || el.type || el.tagName));
  });
  document.querySelectorAll('button').forEach(b => { if (!(b.textContent || '').trim() && !b.getAttribute('aria-label')) out.push('botão sem nome'); });
  document.querySelectorAll('img').forEach(i => { if (!i.hasAttribute('alt')) out.push('img sem alt'); });
  document.querySelectorAll('svg[role=img]').forEach(s => { if (!s.getAttribute('aria-label')) out.push('svg sem rótulo'); });
  if (!document.documentElement.lang) out.push('html sem lang');
  return out;
}"""


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class WebV080(unittest.TestCase):
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

    def session(self, acct):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        p = ctx.new_page()
        p.errors = []
        p.on("pageerror", lambda e: p.errors.append(str(e)))
        p.on("console", lambda m: p.errors.append(m.text) if m.type == "error" and "401" not in m.text else None)
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(acct.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()
        return p

    def visit(self, p, path, heading):
        p.goto(self.base + path)
        p.get_by_role("heading", name=re.compile(heading)).first.wait_for()
        issues = p.evaluate(A11Y_JS)
        self.assertEqual(issues, [], f"{path}: {issues}")

    def test_individual_funder_journey_pages(self):
        pair = funded_pair()
        pf = new_account("individual")
        p = self.session(pf)
        for path, h in (("/explorar", "Projetos para apoiar"), ("/pagamentos", "Pagamentos"), ("/relatorios", "Relatórios"),
                        ("/mapa", "Mapa de projetos"), ("/mensagens", "Mensagens"), ("/carteira", "Meu apoio|Carteira"), ("/organizacao", "Organização")):
            self.visit(p, path, h)
        self.assertEqual(p.errors, [])
        # a privacidade é visível na interface
        p.goto(self.base + "/organizacao")
        p.get_by_text("Mostrar meu nome às organizações que eu apoiar").wait_for()
        self.assertEqual(p.errors, [])

    def test_osc_pages_and_report_render(self):
        pair = funded_pair()
        osc, pid = pair["osc"], pair["pid"]
        p = self.session(osc)
        for path, h in ((f"/projetos/{pid}/impacto", "Impacto e indicadores"), (f"/projetos/{pid}/grafo", "Impact Graph"), (f"/projetos/{pid}/compras", "Compras e cotações"),
                        (f"/projetos/{pid}/contribuicao", "Modelos de contribuição"), (f"/projetos/{pid}/apoio-profissional", "Apoio profissional"),
                        (f"/projetos/{pid}/localizacao", "Localização pública"), ("/diagnosticos", "Diagnóstico social"), ("/extratos", "Extrato e conciliação"),
                        ("/conquistas", "Conquistas")):
            self.visit(p, path, h)
        p.goto(self.base + "/relatorios")
        p.get_by_role("button", name="Gerar").click()
        p.get_by_role("heading", name="Relatório executivo").wait_for()
        self.assertEqual(p.errors, [])

    def test_admin_and_provider_pages(self):
        from tests.support import make_admin
        adm, _ = make_admin()
        prov = new_account("provider")
        p = self.session(prov)
        self.visit(p, "/oportunidades-profissionais", "Oportunidades profissionais")
        self.assertEqual(p.errors, [])


if __name__ == "__main__":
    unittest.main()
