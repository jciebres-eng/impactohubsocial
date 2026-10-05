"""E2E v0.10.1 no Chromium: abas novas da Instituição (OS/OSCIP, instrumentos, formalização e mentoria), rede da solução e PAINEL ADMIN
(filas de instrumentos e de mentoria) — com verificações próprias de acessibilidade (não substituem axe/leitor de tela)."""
import re
import unittest
import uuid
from datetime import date, timedelta

from tests.support import PASSWORD, db_system, make_admin, new_account, server
from tests.test_e2e_v080 import A11Y_JS
from tests.test_e2e_web import DIST, HAVE_PW
from tests.test_v090_solutions import mk
from tests.test_v0101_institutional import add_agreement

if HAVE_PW:
    from playwright.sync_api import sync_playwright


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class WebV0101(unittest.TestCase):
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

    def session(self, acct, viewport=(1280, 900), secret=None):
        ctx = self.browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
        p = ctx.new_page()
        p.errors = []
        p.on("pageerror", lambda e: p.errors.append(str(e)))
        p.on("console", lambda m: p.errors.append(m.text) if m.type == "error" and "401" not in m.text else None)
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(acct.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        if secret:  # administrador: MFA real (TOTP), sem desligar a exigência
            from impacto.security import totp
            p.get_by_label("Código do aplicativo autenticador").fill(totp.totp(secret))
            p.get_by_role("button", name="Confirmar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()
        return p

    def tab(self, p, name):
        p.get_by_role("tab", name=name).click()

    def test_institution_new_tabs_journey(self):
        osc = new_account("osc")
        p = self.session(osc)
        p.goto(self.base + "/instituicao")
        p.get_by_role("heading", name="Instituição").first.wait_for()
        # instrumentos: registra como DECLARADO
        self.tab(p, "Instrumentos")
        p.get_by_label("Tipo").select_option("management_contract")
        p.get_by_label("Órgão ou parte contratante").fill("Secretaria de Saúde (E2E)")
        p.get_by_label("Número do instrumento").fill("CG-E2E-1")
        p.get_by_role("button", name="Registrar").click()
        p.get_by_text("DECLARADO (não verificado)").first.wait_for()
        self.assertNotIn("VERIFICADO\n", p.locator("main").inner_text().replace("NÃO VERIFICADO", ""))
        self.assertEqual(p.evaluate(A11Y_JS), [])
        # perfis OS/OSCIP: sem qualificação, nada é afirmado
        self.tab(p, "OS / OSCIP")
        p.get_by_text("Perfis identificados").wait_for()
        self.assertEqual(p.evaluate(A11Y_JS), [])
        # trilha de formalização e mentoria
        self.tab(p, "Formalização e mentoria")
        p.get_by_text("Trilha de formalização").first.wait_for()
        p.get_by_label("Assunto").select_option("formalization")
        p.get_by_label("O que você precisa?").fill("Preciso de orientação para registrar o estatuto.")
        p.get_by_role("button", name="Enviar pedido").click()
        p.get_by_text("Aberto").first.wait_for()
        self.assertEqual(p.evaluate(A11Y_JS), [])
        self.assertEqual(p.errors, [])

    def test_solution_network_view(self):
        osc = new_account("osc")
        s1 = mk(osc, title="Rede E2E principal", themes=["saude"], ods=[3], uf="MT")
        s2 = mk(osc, title="Rede E2E vizinha", themes=["saude"])
        osc.post(f"/v1/solutions/{s1}/relationships", {"to_id": s2, "rel_type": "complements"})
        p = self.session(new_account("company"))
        p.goto(self.base + f"/solucoes/{s1}")
        p.get_by_role("heading", name=re.compile("Rede E2E principal")).first.wait_for()
        p.get_by_role("button", name="Ver rede de relações").click()
        p.get_by_role("list", name="Relações da solução").wait_for()
        txt = p.locator("[role=dialog]").inner_text() if p.locator("[role=dialog]").count() else p.locator("main").inner_text()
        self.assertIn("Rede E2E vizinha", txt)
        self.assertIn("complementa", txt)
        self.assertEqual(p.errors, [])

    def test_admin_panel_queues(self):
        osc = new_account("osc")
        ag = add_agreement(osc, instrument_number="CG-ADM-1")
        osc.post("/v1/institutional/mentoring", {"topic": "documentation", "message": "Quero ajuda com a documentação da entidade."})
        adm, secret = make_admin()
        with db_system() as d:
            plat = d.scalar("SELECT id::text FROM organizations WHERE kind = 'platform' LIMIT 1")
        pa = self.session(adm, secret=secret)
        pa.evaluate("""async (org) => { const c = document.cookie.split('; ').find(x => x.startsWith('impacto_csrf=')); const t = c ? decodeURIComponent(c.split('=')[1]) : '';
          const r = await fetch('/v1/me/switch-org', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': t}, body: JSON.stringify({org_id: org})}); return r.status; }""", plat)
        pa.goto(self.base + "/admin/institucional")
        pa.get_by_role("heading", name="Institucional").first.wait_for()
        self.assertEqual(pa.evaluate(A11Y_JS), [])
        self.tab(pa, "Instrumentos")
        pa.get_by_label("Instrumentos").or_(pa.get_by_text("Fila de instrumentos")).first.wait_for()
        pa.locator("main select").first.select_option("declared")
        pa.get_by_text("CG-ADM-1").first.wait_for()
        # verificar sem comprovante deve ser recusado e o instrumento continua DECLARADO
        row = pa.locator("tr", has_text="CG-ADM-1")
        row.get_by_label("Nota da decisão").fill("Tentativa sem comprovante válido")
        row.get_by_role("button", name="Verificar").click()
        pa.wait_for_timeout(600)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT verification_status FROM organization_agreements WHERE id = $1", ag["id"]), "declared")
        self.tab(pa, "Mentoria")
        pa.get_by_text("Quero ajuda com a documentação da entidade.").first.wait_for()
        pa.get_by_label("Nota").first.fill("Retornaremos por e-mail.")
        pa.get_by_role("button", name="Em atendimento").first.click()
        pa.wait_for_timeout(600)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT status FROM mentoring_requests WHERE org_id = (SELECT org_id FROM organization_agreements WHERE id = $1) ORDER BY created_at DESC LIMIT 1", ag["id"]), "in_progress")
        # único erro de console esperado: o 422 da tentativa de verificar sem comprovante (recusa correta do servidor)
        self.assertEqual([e for e in pa.errors if "422" not in e], [])
        self.assertEqual(len([e for e in pa.errors if "422" in e]), 1)


if __name__ == "__main__":
    unittest.main()
