"""E2E de navegador — jornadas da baseline técnica que faltavam no navegador: cadastro→login→SAIR,
área bloqueada por tipo de organização, página de Plano (teste/cancelamento/voucher) e área administrativa com MFA real.
Até aqui a cobrança/trial era provada só na API; estas jornadas provam a INTERFACE. Pulado se Playwright ou o build faltarem."""
import re
import unittest
import uuid

from tests.support import PASSWORD, ROOT, db_system, last_token_for, make_admin, new_account, next_cnpj, server

DIST = ROOT / "web" / "dist" / "index.html"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class BaselineE2E(unittest.TestCase):
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

    def page(self, mobile=False):
        ctx = self.browser.new_context(viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 900})
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

    # Jornada: visitante → cadastro → confirmação de e-mail → login → SAIR (sessão realmente encerrada)
    def test_visitor_signup_login_and_logout_ends_the_session(self):
        p = self.page()
        email = f"baseline-{uuid.uuid4().hex[:8]}@teste.org"
        p.goto(self.base + "/cadastro")
        p.get_by_label("Seu nome").fill("Pessoa Baseline")
        p.get_by_label("E-mail").fill(email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_label("Razão social").fill("Associação Baseline E2E")
        p.get_by_label("CNPJ").fill(next_cnpj())
        p.get_by_role("checkbox").check()
        p.get_by_role("button", name="Criar conta").click()
        p.get_by_text("Confirme seu e-mail").wait_for()
        p.goto(f"{self.base}/verificar-email?token={last_token_for(email, '/verificar-email')}")
        p.get_by_text("E-mail confirmado").wait_for()
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()
        p.get_by_role("button", name="Sair").click()
        p.wait_for_url(re.compile(r"/entrar"))
        p.goto(self.base + "/documentos")                       # com a sessão encerrada, área privada volta ao login
        p.wait_for_url(re.compile(r"/entrar\?proximo="))
        self.assertEqual(p.errors, [])

    # Jornada: recurso permitido × recurso bloqueado pelo tipo de organização (sem tela branca)
    def test_user_sees_allowed_area_and_is_blocked_on_another_kinds_area(self):
        osc = new_account("osc")
        p = self.page()
        self.login(p, osc)
        p.goto(self.base + "/projetos")
        p.get_by_role("heading", name="Projetos").first.wait_for()
        p.goto(self.base + "/editais")                          # área de empresa/governo
        p.get_by_text("Esta área não está disponível para este perfil").wait_for()
        p.get_by_role("button", name="Voltar ao início").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()
        p.goto(self.base + "/rota-inexistente-xyz")
        p.get_by_text("Página não encontrada").wait_for()
        self.assertEqual(p.errors, [])

    # Jornada: Plano e cobrança — estado do teste, voucher aplicado na interface e cancelamento que mantém o acesso
    def test_plan_page_shows_trial_applies_voucher_and_cancels_keeping_access(self):
        adm1, _ = make_admin()
        adm2, _ = make_admin()
        batch = adm1.post("/v1/admin/voucher-batches", {"campaign": "E2E " + uuid.uuid4().hex[:5], "quantity": 1,
                                                        "type": "percent_off", "percent": 15, "plan_key": "osc_premium", "max_redemptions": 2})
        self.assertEqual(batch.status, 201, batch)
        self.assertEqual(adm2.post(f"/v1/admin/voucher-batches/{batch.json['batch_id']}/action", {"action": "approve"}).status, 200)
        code = batch.json["codes"][0]
        old = self.state.settings.trial_auto_start
        self.state.settings.trial_auto_start = True
        try:
            osc = new_account("osc")
        finally:
            self.state.settings.trial_auto_start = old
        p = self.page()
        self.login(p, osc)
        p.goto(self.base + "/conta/plano")
        p.get_by_role("heading", name="Plano e cobrança").wait_for()
        p.get_by_text("Teste até").first.wait_for()
        p.get_by_label("Código", exact=True).fill(code)
        p.get_by_role("button", name="Aplicar").click()
        p.get_by_text("Voucher aplicado").wait_for()
        p.get_by_text("Desconto de voucher aguardando a contratação").wait_for()
        p.get_by_role("button", name="Cancelar", exact=True).click()
        p.get_by_text("Nenhuma cobrança será realizada").wait_for()
        p.get_by_role("button", name="Confirmar cancelamento").click()
        p.get_by_text("Cancelamento confirmado").wait_for()
        with db_system() as d:
            t = d.one("SELECT status, canceled_at, trial_end > now() AS ainda_vale FROM org_trials WHERE org_id = $1", osc.org_id)
        self.assertIsNotNone(t["canceled_at"], "cancelamento não foi registrado")
        self.assertTrue(t["ainda_vale"], "cancelar encurtou o acesso já concedido")
        self.assertTrue(osc.get("/v1/me").json["entitlements"]["features"], "acesso caiu imediatamente após cancelar")
        self.assertEqual(p.errors, [])

    # Jornada: administração com MFA real (TOTP) → visão geral e auditoria
    def test_admin_logs_in_with_mfa_and_reaches_overview_and_audit(self):
        from impacto.security import totp
        adm, secret = make_admin()
        p = self.page()
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(adm.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_label("Código do aplicativo autenticador").fill(totp.totp(secret))
        p.get_by_role("button", name="Confirmar").click()
        p.get_by_role("heading", name=re.compile("Olá")).first.wait_for()
        # a interface libera a administração quando a organização ATIVA é a plataforma: troca pelo seletor do menu
        p.get_by_label("Organização ativa").select_option(label="Plataforma")
        p.get_by_role("heading", name="Administração").first.wait_for()
        p.goto(self.base + "/admin/auditoria")
        p.get_by_role("heading", name="Auditoria").first.wait_for()
        p.goto(self.base + "/admin/central")
        p.get_by_role("heading", name="Central de Conhecimento").first.wait_for()
        p.goto(self.base + "/admin/central/suporte")
        p.get_by_role("heading", name="Fila de suporte").first.wait_for()
        self.assertEqual(p.errors, [])


if __name__ == "__main__":
    unittest.main()
