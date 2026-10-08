"""v0.25.0 — responsividade: cada perfil abre as telas do PRÓPRIO menu na largura de um telefone.

Critério objetivo, não opinião: na largura de 390 px a PÁGINA não pode ganhar rolagem horizontal
(tabela larga rola dentro do próprio contêiner, a página não), não pode haver erro de JavaScript e o
menu tem de abrir. Grava `docs/evidence/responsivo_v0250/resumo.json` e uma captura por perfil.

Não prova que a tela é boa no telefone — prova que nada vaza da tela e que ela não quebra.
"""
from __future__ import annotations

import json
import unittest

from tests.support import PASSWORD, ROOT, server
from tests import screen_crawler as robo
from tests.test_v0250_todas_as_telas import DIST, HAVE_PW, popular_demonstracao

EVID = ROOT / "docs" / "evidence" / "responsivo_v0250"
if HAVE_PW:
    from playwright.sync_api import sync_playwright

#: o elemento que mais passa da largura, para o relatório dizer O QUE vazou
VAZAMENTO_JS = """() => {
  const w = window.innerWidth;
  if (document.documentElement.scrollWidth <= w + 1) return null;
  let pior = null, max = w;
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.right > max + 1 && getComputedStyle(el).position !== 'fixed') {
      let rola = false;
      for (let n = el.parentElement; n; n = n.parentElement) {
        const o = getComputedStyle(n).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') { rola = true; break; } }
      if (!rola) { max = r.right; pior = el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').join('.') : ''); }
    }
  }
  return {largura_da_pagina: document.documentElement.scrollWidth, janela: w, elemento: pior};
}"""


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class EveryMenuScreenFitsAPhoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        cls._old = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base
        popular_demonstracao(cls.base, cls.state)
        from impacto import seed_dev
        from impacto.db.pool import DbContext
        cls.emails = seed_dev.DEMO_EMAILS
        with cls.state.pool.tx(DbContext(system=True)) as c:
            cls.segredo = cls.state.cipher.decrypt(c.scalar("SELECT mfa_secret_enc FROM users WHERE email = $1", cls.emails["admin"]))

    @classmethod
    def tearDownClass(cls):
        cls.state.settings.public_base_url = cls._old

    def test_no_menu_screen_scrolls_sideways_on_a_phone(self):
        from tests.support import fresh_totp
        resultado, falhas = {}, []
        EVID.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                for persona in ("osc", "company", "provider", "government", "individual", "admin"):
                    r = robo.Robo(browser, self.base, PASSWORD, lambda: fresh_totp(self.segredo))
                    # o robô cria a página em largura de computador; aqui, telefone
                    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
                    p = ctx.new_page()
                    p.ev = {"js": [], "5xx": [], "4xx": [], "api": 0}
                    p.on("pageerror", lambda e, p=p: p.ev["js"].append(str(e)))
                    r.paginas[persona] = p
                    p.goto(self.base + "/entrar")
                    p.get_by_label("E-mail").fill(self.emails[persona])
                    p.get_by_label("Senha").fill(PASSWORD)
                    p.get_by_role("button", name="Entrar").click()
                    p.wait_for_selector('nav#rail, .portal, h1:has-text("Verificação em duas etapas")', timeout=20000)
                    if p.get_by_role("heading", name="Verificação em duas etapas").count():
                        p.get_by_label("Código do aplicativo autenticador").fill(fresh_totp(self.segredo))
                        p.get_by_role("button", name="Confirmar").click()
                        p.wait_for_selector("nav#rail, .portal", timeout=20000)
                    p.wait_for_load_state("networkidle")
                    rotas = p.evaluate("() => [...new Set([...document.querySelectorAll('nav#rail a[href]')]"
                                       ".map(a => a.getAttribute('href')).filter(h => h && h.startsWith('/')))]")
                    p.screenshot(path=str(EVID / f"{persona}_telefone.png"))
                    vazaram = {}
                    for rota in rotas:
                        p.ev["js"].clear()
                        p.goto(self.base + rota, wait_until="domcontentloaded")
                        try:
                            p.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:  # noqa: BLE001
                            pass
                        v = p.evaluate(VAZAMENTO_JS)
                        if v:
                            vazaram[rota] = v
                            falhas.append(f"{persona} {rota}: página {v['largura_da_pagina']}px em janela {v['janela']}px ({v['elemento']})")
                        if p.ev["js"]:
                            falhas.append(f"{persona} {rota}: erro de JavaScript {p.ev['js'][0][:120]}")
                    resultado[persona] = {"telas_do_menu": len(rotas), "com_rolagem_lateral": vazaram}
                    ctx.close()
            finally:
                browser.close()
        total = sum(x["telas_do_menu"] for x in resultado.values())
        (EVID / "resumo.json").write_text(json.dumps({"largura": 390, "telas_visitadas": total, "por_perfil": resultado,
                                                      "falhas": falhas}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.assertGreater(total, 150, "poucas telas de menu: o login no telefone falhou?")
        self.assertEqual(falhas, [], "\n" + "\n".join(falhas))


@unittest.skipUnless(HAVE_PW, "Playwright indisponível")
class TheOverflowDetectorDetectsTests(unittest.TestCase):
    """Controle positivo: "nenhuma tela vaza" só vale se o detector acusa um vazamento quando há."""

    def test_a_wide_block_is_reported_and_a_scrolling_table_is_not(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                p = browser.new_page(viewport={"width": 390, "height": 800})
                p.set_content('<div style="overflow-x:auto"><table style="width:900px"><tr><td>ok</td></tr></table></div>')
                self.assertIsNone(p.evaluate(VAZAMENTO_JS), "tabela que rola no próprio contêiner não é vazamento")
                p.set_content('<div class="largo" style="width:900px">vaza</div>')
                v = p.evaluate(VAZAMENTO_JS)
            finally:
                browser.close()
        self.assertIsNotNone(v)
        self.assertEqual(v["elemento"], "div.largo")
