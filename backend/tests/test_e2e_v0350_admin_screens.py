"""v0.35.0 — as telas de administração que esta versão mexeu passam nas verificações PRÓPRIAS de acessibilidade, no Chromium.

Por que existe: o job `pilha-do-zero` do PR #8 (axe-core com `--axe-trava`) reprovou `/admin/identidade` com
`select-name` — o seletor "Aguardando decisão / Já decididas" que o lote H pôs no cabeçalho da fila não tinha nome
acessível. O axe-core não é baixável neste ambiente (registro npm bloqueado), então a suíte local não tinha como ver.
Este teste usa a verificação própria do projeto (`A11Y_JS`, rótulo de todo controle de formulário) e falha no código
anterior à correção. Não substitui o axe do CI nem leitor de tela.
"""
import re
import unittest

from tests.support import PASSWORD, db_system, fresh_totp, make_admin, server
from tests.test_e2e_v080 import A11Y_JS
from tests.test_e2e_web import DIST, HAVE_PW

if HAVE_PW:
    from playwright.sync_api import sync_playwright

#: telas de administração alteradas na v0.35.0 (lotes B, C e H) e o título que confirma que a tela carregou
TELAS = (("/admin/identidade", "Identidade"), ("/admin/risco", "Sinais de risco"),
         ("/admin/doacoes", "Revisão de campanhas"), ("/admin/doacoes/risco", "Casos de risco"))


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class AdminScreensTouchedInThisVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        cls._old = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base      # origem confiável = o servidor de teste (como os demais E2E)
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old

    def _admin_page(self):
        adm, secret = make_admin()
        with db_system() as d:
            plat = d.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1")
        p = self.browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(adm.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_label("Código do aplicativo autenticador").fill(fresh_totp(secret))
        p.get_by_role("button", name="Confirmar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()
        p.evaluate("""async (org) => { const c = document.cookie.split('; ').find(x => x.startsWith('impacto_csrf='));
          const t = c ? decodeURIComponent(c.split('=')[1]) : '';
          await fetch('/v1/me/switch-org', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': t},
                                            body: JSON.stringify({org_id: org})}); }""", plat)
        return p

    def test_every_form_control_on_the_touched_admin_screens_has_a_name(self):
        p = self._admin_page()
        achados = {}
        for rota, titulo in TELAS:
            p.goto(self.base + rota)
            p.locator("h1", has_text=re.compile(titulo, re.I)).first.wait_for()
            p.wait_for_timeout(400)
            falhas = p.evaluate(A11Y_JS)
            if falhas:
                achados[rota] = falhas
        self.assertEqual(achados, {}, f"telas com controle sem nome acessível: {achados}")

    def test_the_identity_queue_filter_is_named_and_switches_to_decided(self):
        p = self._admin_page()
        p.goto(self.base + "/admin/identidade")
        filtro = p.get_by_label("Quais verificações mostrar")
        filtro.wait_for()
        filtro.select_option("decided")
        p.wait_for_timeout(400)
        self.assertEqual(p.evaluate(A11Y_JS), [])


if __name__ == "__main__":
    unittest.main()
