"""A demonstração completa, executada de verdade: servidor real, banco semeado, navegador real.

O QUE ESTE TESTE PROVA — E O QUE NÃO PROVA

Prova que, com o `seed-demo` aplicado, CADA persona de demonstração entra pelo navegador, vê a barra
de navegação com a marca oficial renderizada (a imagem carregou, não é um `alt` vazio), e consegue
abrir TODA tela que o próprio menu dela oferece sem que o servidor responda 5xx e sem erro de
JavaScript na página. Faz isso nos temas claro e escuro, e também na largura de telefone.

Não prova que cada tela está correta, bonita ou completa: prova que ela abre e que o backend por
trás dela responde. Uma tela de menu que responda 4xx para a própria persona que a vê no menu é
registrada no relatório de evidência — é informação para o Designer e para o produto —, mas não
derruba o teste, porque há 4xx deliberados (plano, permissão granular, MFA).

Pulado quando Playwright/Chromium ou o build do front não existem — e diz isso, em vez de passar.
"""
from __future__ import annotations

import json
import os
import unittest
from datetime import UTC, datetime

from tests.support import PASSWORD, ROOT, server

DIST = ROOT / "web" / "dist" / "index.html"
EVIDENCIA = ROOT / "docs" / "evidence" / "demo_v0240"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class TheWholeDemoRunsForEveryPersonaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        cls._old_base = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base
        # A senha da demonstração vem de DEMO_PASSWORD; aqui é a mesma senha forte dos testes, para
        # que nenhuma senha de demonstração precise estar escrita neste arquivo.
        os.environ["DEMO_PASSWORD"] = PASSWORD
        from impacto import seed_dev
        r = seed_dev.seed(cls.state)
        assert r["status"] in ("seeded", "already_seeded"), r
        cls.emails = seed_dev.DEMO_EMAILS
        cls.segredo_totp = cls._segredo_totp_do_admin()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.relatorio: dict = {"gerado_em": datetime.now(UTC).isoformat(), "personas": {}}
        EVIDENCIA.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old_base
        (EVIDENCIA / "relatorio.json").write_text(json.dumps(cls.relatorio, ensure_ascii=False, indent=1) + "\n",
                                                   encoding="utf-8")

    # ------------------------------------------------------------------ apoio
    @classmethod
    def _segredo_totp_do_admin(cls) -> str:
        """O segredo TOTP que o seed cadastrou nas contas internas, lido do banco e decifrado pelo
        cifrador da aplicação — e não de uma variável deste processo, porque outro módulo de teste pode
        ter semeado antes, com segredo gerado na hora. É o MESMO caminho que `mfa_login` percorre."""
        from impacto.db.pool import DbContext
        with cls.state.pool.tx(DbContext(system=True)) as c:
            enc = c.scalar("SELECT mfa_secret_enc FROM users WHERE email = $1", cls.emails["admin"])
        assert enc, "o seed não cadastrou segundo fator no administrador da demonstração"
        return cls.state.cipher.decrypt(enc)

    def _pagina(self, *, mobile=False, tema: str | None = None):
        ctx = self.browser.new_context(viewport={"width": 390, "height": 844} if mobile else {"width": 1366, "height": 900},
                                       color_scheme=tema or "light")
        p = ctx.new_page()
        p.erros, p.cincos, p.quatros = [], [], []
        p.on("pageerror", lambda e: p.erros.append(str(e)))
        p.on("console", lambda m: p.erros.append(m.text) if m.type == "error" and "401" not in m.text
             and "Failed to load resource" not in m.text else None)

        def resposta(r):
            if r.status >= 500:
                p.cincos.append((r.status, r.url))
            elif r.status >= 400 and "/v1/" in r.url and r.status != 401:
                p.quatros.append((r.status, r.url))
        p.on("response", resposta)
        return p

    def _entrar(self, p, email: str):
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        # Contas internas passam pela verificação em duas etapas DE VERDADE: código TOTP calculado do
        # segredo que o seed cadastrou, verificado pelo servidor com `verify_once` (queima o código).
        # `.auth h1` genérico casava o "Entrar" ainda na tela, antes da resposta, e a etapa do código
        # era pulada em silêncio — as 10 contas internas "entravam" e paravam na verificação.
        p.wait_for_selector('nav#rail, .portal, h1:has-text("Verificação em duas etapas")', timeout=15000)
        if p.get_by_role("heading", name="Verificação em duas etapas").count():
            from impacto.security import totp
            p.get_by_label("Código do aplicativo autenticador").fill(totp.totp(self.segredo_totp))
            p.get_by_role("button", name="Confirmar").click()
            p.wait_for_selector("nav#rail, .portal", timeout=15000)
        p.wait_for_load_state("networkidle")

    def _marca_carregou(self, p) -> bool:
        return bool(p.evaluate("""() => { const i = document.querySelector('.brand img');
            return !!i && i.complete && i.naturalWidth > 0 && getComputedStyle(i).display !== 'none'; }"""))

    def _rotas_do_menu(self, p) -> list[str]:
        hrefs = p.evaluate("() => [...document.querySelectorAll('nav#rail a[href]')].map(a => a.getAttribute('href'))")
        vistos, fora = set(), []
        for h in hrefs:
            if h and h.startswith("/") and h not in vistos:
                vistos.add(h)
                fora.append(h)
        return fora

    # ------------------------------------------------------------------ provas
    def test_every_persona_opens_every_menu_screen_with_the_official_brand(self):
        falhas = []
        for papel, email in self.emails.items():
            p = self._pagina()
            try:
                self._entrar(p, email)
            except Exception as exc:  # noqa: BLE001 — a mensagem útil é qual persona não entrou
                falhas.append(f"{papel}: não entrou — {str(exc)[:160]}")
                p.context.close()
                continue
            tem_rail = p.locator("nav#rail").count() > 0
            if not tem_rail:
                # A primeira versão deste teste deixava passar persona sem menu (contava zero telas e
                # seguia): as 10 contas internas paravam fora do shell e o teste ficava verde. Agora
                # persona sem barra de navegação é falha, com a URL onde parou.
                falhas.append(f"{papel}: entrou mas não chegou ao shell com menu (parou em {p.url.split(self.base)[-1]})")
            rotas = self._rotas_do_menu(p) if tem_rail else []
            registro = {"email": email, "tem_menu": tem_rail, "telas_do_menu": len(rotas),
                        "marca_renderizada": self._marca_carregou(p) if tem_rail else None,
                        "telas_ok": [], "telas_4xx": {}, "telas_5xx": {}, "erros_js": {}}
            if tem_rail and not registro["marca_renderizada"]:
                falhas.append(f"{papel}: a marca oficial não renderizou na barra lateral")
            for rota in rotas:
                p.cincos.clear(); p.quatros.clear(); p.erros.clear()
                p.goto(self.base + rota)
                try:
                    p.wait_for_load_state("networkidle", timeout=15000)
                except Exception:  # noqa: BLE001 — rede que não aquieta vira registro, não exceção
                    pass
                if p.cincos:
                    registro["telas_5xx"][rota] = p.cincos[:]
                    falhas.append(f"{papel} {rota}: servidor respondeu 5xx {p.cincos[:2]}")
                if p.erros:
                    registro["erros_js"][rota] = p.erros[:3]
                    falhas.append(f"{papel} {rota}: erro de JavaScript {p.erros[:1]}")
                if p.quatros:
                    registro["telas_4xx"][rota] = sorted({f"{s} {u.split(self.base)[-1][:90]}" for s, u in p.quatros})
                if not p.cincos and not p.erros:
                    registro["telas_ok"].append(rota)
            self.relatorio["personas"][papel] = registro
            if papel == "osc":
                p.goto(self.base + "/")
                p.wait_for_load_state("networkidle")
                p.screenshot(path=str(EVIDENCIA / "osc_inicio_claro.png"), full_page=False)
            if papel == "admin":
                p.goto(self.base + "/admin")
                p.wait_for_load_state("networkidle")
                p.screenshot(path=str(EVIDENCIA / "admin_visao_geral_claro.png"))
            p.context.close()
        total = sum(r["telas_do_menu"] for r in self.relatorio["personas"].values())
        self.relatorio["total_telas_de_menu_visitadas"] = total
        self.assertGreater(total, 100, "poucas telas de menu visitadas: o seed ou o login não funcionou")
        self.assertEqual(falhas, [], "\n".join(falhas))

    def test_the_dark_theme_and_the_phone_width_render_the_brand_too(self):
        # tema escuro
        p = self._pagina(tema="dark")
        self._entrar(p, self.emails["osc"])
        self.assertTrue(self._marca_carregou(p), "marca não renderizou no tema escuro")
        fundo = p.evaluate("() => getComputedStyle(document.body).backgroundColor")
        self.assertNotIn(fundo, ("rgb(246, 248, 249)", "rgb(255, 255, 255)"), f"tema escuro não aplicou: fundo {fundo}")
        p.screenshot(path=str(EVIDENCIA / "osc_inicio_escuro.png"))
        self.assertEqual(p.erros, [])
        p.context.close()
        # telefone: barra lateral fechada, abre pelo botão de menu, marca no cabeçalho e na barra
        p = self._pagina(mobile=True)
        self._entrar(p, self.emails["osc"])
        largura = p.evaluate("document.documentElement.scrollWidth")
        self.assertLessEqual(largura, 390, f"rolagem horizontal em 390px: {largura}")
        p.get_by_role("button", name="Menu").click()
        p.wait_for_selector("nav#rail.rail-open")
        p.wait_for_timeout(400)  # a barra desliza em 200ms; captura no meio da transição não serve de evidência
        p.screenshot(path=str(EVIDENCIA / "osc_telefone_menu_aberto.png"))
        self.assertEqual(p.erros, [])
        p.context.close()
        # entrada (sem sessão): marca sobre o painel navy
        p = self._pagina()
        p.goto(self.base + "/entrar")
        p.wait_for_load_state("networkidle")
        self.assertTrue(self._marca_carregou(p), "marca não renderizou na tela de entrar")
        p.screenshot(path=str(EVIDENCIA / "entrar.png"))
        p.context.close()

    def test_the_white_on_yellow_rule_holds_on_every_primary_button(self):
        """A identidade proíbe texto branco sobre amarelo. Medido no botão renderizado, não no CSS."""
        p = self._pagina()
        self._entrar(p, self.emails["osc"])
        p.goto(self.base + "/projetos")
        p.wait_for_load_state("networkidle")
        cores = p.evaluate("""() => [...document.querySelectorAll('.btn-primary')].map(b => {
            const s = getComputedStyle(b); return [s.backgroundColor, s.color]; })""")
        for fundo, texto in cores:
            self.assertNotEqual(texto, "rgb(255, 255, 255)", f"texto branco sobre {fundo}")
        p.context.close()
