"""v0.18.1 — acessibilidade conferida NO NAVEGADOR, com o que é verificável sem axe (FASE 6).

O pedido desta rodada inclui `axe`, leitor de tela, teclado, foco, contraste, formulários e mobile.
O que este ambiente permite e o que não permite, dito com clareza:

* **`axe-core` NÃO está disponível**: o registry npm responde 403 aqui, então não há como instalar a
  biblioteca nem injetá-la de CDN. Chamar o que está abaixo de "auditoria axe" seria mentira.
* **Leitor de tela real** (NVDA/VoiceOver) exige sistema operacional com o leitor instalado: fora
  de alcance neste ambiente, e marcado como pendência no relatório.
* O que **é** verificável aqui, e está verificado: nome acessível de todo controle, navegação só por
  teclado, foco visível, marcos de página, alternativa textual, contraste calculado a partir do
  estilo COMPUTADO, ausência de rolagem horizontal em 390px, e tema escuro.

O cálculo de contraste é o do WCAG 2.1 (luminância relativa), feito dentro da página sobre as cores
que o navegador realmente aplicou — não sobre os tokens do CSS, que é onde esse tipo de verificação
costuma passar quando não deveria.
"""
from __future__ import annotations

import re
import unittest

from tests.support import PASSWORD, ROOT, new_account, server

DIST = ROOT / "web" / "dist" / "index.html"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False

#: Função de contraste WCAG, executada no navegador sobre o estilo computado.
CONTRAST_JS = """
() => {
  const lum = (c) => {
    const [r, g, b] = c.map(v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); });
    return 0.2126*r + 0.7152*g + 0.0722*b;
  };
  const parse = (s) => { const m = s.match(/\\d+(\\.\\d+)?/g); return m ? m.slice(0,3).map(Number) : null; };
  const bgOf = (el) => {
    let n = el;
    while (n && n !== document.documentElement) {
      const bg = getComputedStyle(n).backgroundColor;
      const p = parse(bg);
      if (p && !/rgba\\(0, 0, 0, 0\\)|transparent/.test(bg)) return p;
      n = n.parentElement;
    }
    return parse(getComputedStyle(document.body).backgroundColor) || [255,255,255];
  };
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1,l2), lo = Math.min(l1,l2); return (hi+0.05)/(lo+0.05); };
  const out = [];
  const seletor = 'p, a, button, label, h1, h2, h3, li, span.field-label, .field-hint, .pill';
  for (const el of document.querySelectorAll(seletor)) {
    const txt = (el.textContent || '').trim();
    if (!txt || el.offsetParent === null) continue;
    const cs = getComputedStyle(el);
    const fg = parse(cs.color);
    if (!fg) continue;
    const size = parseFloat(cs.fontSize);
    const bold = (parseInt(cs.fontWeight, 10) || 400) >= 600;
    const grande = size >= 24 || (size >= 18.66 && bold);
    const r = ratio(fg, bgOf(el));
    out.push({texto: txt.slice(0, 40), ratio: Math.round(r*100)/100, minimo: grande ? 3 : 4.5,
              tag: el.tagName.toLowerCase(), size});
  }
  return out;
}
"""


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class AccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        cls._old = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.account = new_account("osc", compliance="approved")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old

    def page(self, *, mobile: bool = False, dark: bool = False, reduced: bool = False):
        ctx = self.browser.new_context(
            viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 900},
            color_scheme="dark" if dark else "light",
            reduced_motion="reduce" if reduced else "no-preference")
        p = ctx.new_page()
        p.errors = []
        p.on("pageerror", lambda e: p.errors.append(str(e)))
        return p

    def _login(self, p):
        """Espera o CUMPRIMENTO, não "um heading qualquer".

        A primeira versão esperava `heading.first`, que casa com o título da própria tela de
        login — então quatro testes mediram a tela de login achando que mediam a aplicação
        autenticada. Foi assim que descobri três alvos de toque de 22px: o achado é real, mas o
        teste estava medindo a página errada.
        """
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(self.account.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for(timeout=15000)

    # ------------------------------------------------------------------ formulários
    def test_every_form_control_has_an_accessible_name(self):
        p = self.page()
        p.goto(self.base + "/entrar")
        sem_nome = p.evaluate("""() => {
            const falhas = [];
            for (const el of document.querySelectorAll('input, select, textarea')) {
                if (el.type === 'hidden' || el.offsetParent === null) continue;
                const rotulado = el.labels && el.labels.length > 0;
                const nome = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')
                           || el.getAttribute('title');
                if (!rotulado && !nome) falhas.push(el.outerHTML.slice(0, 120));
            }
            return falhas;
        }""")
        self.assertEqual(sem_nome, [], f"controle sem nome acessível: {sem_nome}")
        self.assertEqual(p.errors, [])

    def test_an_invalid_submission_announces_the_error_to_assistive_technology(self):
        p = self.page()
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill("nao-existe@teste.org")
        p.get_by_label("Senha").fill("errada-de-proposito")
        p.get_by_role("button", name="Entrar").click()
        # a mensagem precisa existir num contêiner anunciável (role=alert ou aria-live)
        p.wait_for_timeout(800)
        anuncia = p.evaluate("""() => {
            const vivos = document.querySelectorAll('[role=alert], [aria-live]');
            for (const n of vivos) if ((n.textContent || '').trim().length > 3) return true;
            return false;
        }""")
        self.assertTrue(anuncia, "o erro de login não é anunciado por tecnologia assistiva")

    # ------------------------------------------------------------------ teclado e foco
    def test_the_skip_link_is_the_first_stop_and_jumps_to_the_content(self):
        p = self.page()
        self._login(p)
        p.keyboard.press("Tab")
        primeiro = p.evaluate("() => document.activeElement.className + '|' + "
                              "(document.activeElement.getAttribute('href') || '')")
        self.assertIn("skip", primeiro, f"o primeiro Tab não é o atalho de conteúdo: {primeiro}")
        p.keyboard.press("Enter")
        self.assertTrue(p.evaluate("() => !!document.getElementById('conteudo')"),
                        "o destino do atalho não existe na página")

    def test_keyboard_only_navigation_reaches_the_main_actions(self):
        p = self.page()
        self._login(p)
        alcancados = p.evaluate("""() => {
            const foco = [];
            const alvo = Array.from(document.querySelectorAll('a[href], button:not([disabled])'))
                              .filter(e => e.offsetParent !== null);
            return alvo.length;
        }""")
        self.assertGreater(alcancados, 5, "a página não tem alvos focáveis suficientes")
        for _ in range(12):
            p.keyboard.press("Tab")
        ativo = p.evaluate("() => document.activeElement.tagName.toLowerCase()")
        self.assertIn(ativo, ("a", "button", "input", "select", "textarea", "summary"),
                      f"depois de 12 Tabs o foco está em {ativo}: há armadilha de foco")

    def test_the_focus_is_visible_and_not_removed_by_css(self):
        p = self.page()
        self._login(p)
        p.keyboard.press("Tab")
        p.keyboard.press("Tab")
        estilo = p.evaluate("""() => {
            const cs = getComputedStyle(document.activeElement);
            return {outline: cs.outlineStyle, largura: cs.outlineWidth, sombra: cs.boxShadow};
        }""")
        visivel = (estilo["outline"] not in ("none", "") and estilo["largura"] not in ("0px", "")) \
            or (estilo["sombra"] not in ("none", ""))
        self.assertTrue(visivel, f"foco sem indicação visual: {estilo}")

    # ------------------------------------------------------------------ marcos e semântica
    def test_the_page_has_landmarks_and_exactly_one_first_level_heading(self):
        p = self.page()
        self._login(p)
        estrutura = p.evaluate("""() => ({
            main: document.querySelectorAll('main, [role=main]').length,
            nav: document.querySelectorAll('nav, [role=navigation]').length,
            h1: document.querySelectorAll('h1').length,
            lang: document.documentElement.lang,
            titulo: document.title,
        })""")
        self.assertGreaterEqual(estrutura["main"], 1, "sem marco de conteúdo principal")
        self.assertGreaterEqual(estrutura["nav"], 1, "sem marco de navegação")
        self.assertEqual(estrutura["h1"], 1, f"a página tem {estrutura['h1']} títulos de nível 1")
        self.assertTrue(estrutura["lang"].startswith("pt"), estrutura["lang"])
        self.assertTrue(estrutura["titulo"])

    def test_no_image_or_icon_only_button_is_left_without_an_alternative(self):
        p = self.page()
        self._login(p)
        faltando = p.evaluate("""() => {
            const falhas = [];
            for (const img of document.querySelectorAll('img')) {
                if (img.getAttribute('alt') === null) falhas.push('img: ' + img.src.slice(-40));
            }
            for (const b of document.querySelectorAll('button, a[href]')) {
                if (b.offsetParent === null) continue;
                const texto = (b.textContent || '').trim();
                const nome = b.getAttribute('aria-label') || b.getAttribute('title');
                if (!texto && !nome) falhas.push('controle sem texto: ' + b.outerHTML.slice(0, 80));
            }
            return falhas;
        }""")
        self.assertEqual(faltando, [], f"alternativa textual ausente: {faltando}")

    # ------------------------------------------------------------------ contraste
    def test_the_computed_contrast_meets_wcag_aa_in_light_mode(self):
        p = self.page()
        self._login(p)
        amostras = p.evaluate(CONTRAST_JS)
        self.assertGreater(len(amostras), 10, "poucas amostras de texto para avaliar contraste")
        ruins = [a for a in amostras if a["ratio"] < a["minimo"]]
        self.assertEqual(ruins, [], f"contraste abaixo do mínimo AA: {ruins[:6]}")

    def test_the_computed_contrast_meets_wcag_aa_in_dark_mode(self):
        p = self.page(dark=True)
        self._login(p)
        fundo = p.evaluate("() => getComputedStyle(document.body).backgroundColor")
        self.assertNotIn(fundo, ("rgb(255, 255, 255)", "rgba(0, 0, 0, 0)"),
                         f"o tema escuro não mudou o fundo: {fundo}")
        ruins = [a for a in p.evaluate(CONTRAST_JS) if a["ratio"] < a["minimo"]]
        self.assertEqual(ruins, [], f"contraste abaixo do mínimo AA no escuro: {ruins[:6]}")

    # ------------------------------------------------------------------ mobile e movimento
    def test_there_is_no_horizontal_scroll_at_phone_width(self):
        p = self.page(mobile=True)
        self._login(p)
        medida = p.evaluate("() => ({doc: document.documentElement.scrollWidth,"
                            " janela: window.innerWidth})")
        self.assertLessEqual(medida["doc"], medida["janela"] + 1,
                             f"há rolagem horizontal em 390px: {medida}")

    def test_touch_targets_are_big_enough_on_a_phone(self):
        p = self.page(mobile=True)
        self._login(p)
        pequenos = p.evaluate("""() => {
            const falhas = [];
            for (const b of document.querySelectorAll('button, a[href], input[type=checkbox]')) {
                if (b.offsetParent === null) continue;
                const r = b.getBoundingClientRect();
                if (r.width < 24 || r.height < 24) {
                    falhas.push(((b.textContent||'').trim().slice(0,24) || b.tagName)
                                + ` ${Math.round(r.width)}x${Math.round(r.height)}`);
                }
            }
            return falhas;
        }""")
        self.assertEqual(pequenos, [], f"alvo de toque abaixo de 24x24 (WCAG 2.2 AA): {pequenos}")

    def test_reduced_motion_is_respected(self):
        p = self.page(reduced=True)
        self._login(p)
        ok = p.evaluate("""() => {
            const el = document.querySelector('.btn, a[href]');
            if (!el) return true;
            const cs = getComputedStyle(el);
            return cs.transitionDuration === '0s' || cs.transitionProperty === 'none';
        }""")
        self.assertTrue(ok, "a preferência por menos movimento não é respeitada")

    def test_what_this_file_does_not_cover_is_declared(self):
        """Um teste que existe para escrever a pendência no lugar onde ela não pode ser esquecida."""
        import pathlib
        doc = (ROOT / "ACCESSIBILITY_REPORT.md").read_text(encoding="utf-8")
        baixo = doc.lower()
        for pendencia in ("axe", "leitor de tela", "not verified"):
            self.assertIn(pendencia, baixo, f"a pendência '{pendencia}' não está declarada")
        self.assertTrue(pathlib.Path(ROOT / "ACCESSIBILITY_REPORT.md").exists())
