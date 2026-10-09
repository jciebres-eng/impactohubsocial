"""E2E no navegador (Chromium/Playwright) da Central de IA v0.28.0, contra o servidor que serve a SPA compilada.

Jornada 1 — OSC: ficha do projeto → "O que este projeto traz de novo" → a tela de confirmação mostra custo, quem paga e
saldo ANTES de executar → confirma → página da análise com dimensões separadas e o aviso de que nada prova plágio →
contesta → Central de IA mostra a execução, o extrato e a cota.
Jornada 2 — pedido de crédito em modo piloto (sem pagamento) e a administração aprovando como concessão em
/admin/ia/financeiro; o painel diz o que NÃO está medido.
Jornada 3 — sem fonte de custeio a tela diz por que não dá e o que fazer; nada é executado.
Pulado se Playwright ou o build não existirem.
"""
import re
import unittest

from tests.support import PASSWORD, ROOT, db_system, make_admin, new_account, server
from tests.test_v0280_ai_usage_control import _projeto

DIST = ROOT / "web" / "dist" / "index.html"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class AiCenterE2E(unittest.TestCase):
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

    def page(self, mobile=False):
        ctx = self.browser.new_context(viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 900})
        p = ctx.new_page()
        p.errors = []
        p.on("pageerror", lambda e: p.errors.append(str(e)))
        p.on("console", lambda m: p.errors.append(m.text) if m.type == "error" and "401" not in m.text and "402" not in m.text and "404" not in m.text else None)
        return p

    def login(self, p, acct):
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(acct.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for()

    def test_originality_from_the_project_page_with_confirmation_then_dispute_and_center(self):
        osc = new_account("osc")
        pid = _projeto(osc, title="Leitura no bairro E2E")
        p = self.page()
        self.login(p, osc)
        p.goto(f"{self.base}/projetos/{pid}")
        p.get_by_role("heading", name="Originalidade, similaridade e complementaridade").wait_for()
        p.get_by_role("button", name="O que este projeto traz de novo").click()
        # confirmação ANTES de executar: custo, quem paga, saldo, critério de conclusão, "se falhar"
        dlg = p.get_by_role("dialog")
        dlg.get_by_role("button", name="Confirmar e executar").wait_for()
        self.assertIn("49 créditos", dlg.inner_text())
        self.assertIn("cota gratuita", dlg.inner_text())
        self.assertIn("nada é cobrado", dlg.inner_text())
        self.assertIn("motor local", dlg.inner_text())
        dlg.get_by_role("button", name="Confirmar e executar").click()
        p.get_by_role("heading", name="O que este projeto traz de novo").wait_for()
        self.assertIn("≠ plágio ≠ fraude", p.inner_text("main"))
        self.assertIn("confiança", p.inner_text("main"))
        p.get_by_role("button", name="Contestar ou corrigir").click()
        p.get_by_role("dialog").get_by_role("textbox").fill("O território comparado é outro distrito; a comparação ignora isso.")
        p.get_by_role("dialog").get_by_role("button", name="Enviar").click()
        p.get_by_text("aguardando revisão humana").wait_for()
        # Central de IA: execução no histórico, extrato com o consumo, cota debitada
        p.goto(self.base + "/ia")
        p.get_by_role("heading", name="Extrato de créditos").wait_for()
        txt = p.inner_text("main")
        self.assertIn("similarity.single", txt)
        self.assertIn("concluída e conciliada", txt)
        self.assertIn("-49", txt)
        self.assertIn("Cota de boas-vindas", txt)
        self.assertEqual(p.errors, [])

    def test_without_funding_the_dialog_explains_and_nothing_runs(self):
        osc = new_account("osc")
        pid = _projeto(osc, title="Projeto sem crédito E2E")
        with db_system() as d:
            # esgota a cota: consome os 70 promocionais com um ajuste administrativo de teste
            d.run("INSERT INTO ai_credit_ledger(org_id, delta, reason, bucket, idempotency_key, note) VALUES ($1, -60, 'adjustment', 'promotional', $2, 'teste: zera boas-vindas')", osc.org_id, "adj1:" + osc.org_id)
        p = self.page()
        self.login(p, osc)
        p.goto(self.base + "/ia")   # concede as cotas (60 + 10) e aplica o ajuste já lançado → sobram 10
        p.get_by_role("heading", name="Extrato de créditos").wait_for()
        p.goto(f"{self.base}/projetos/{pid}")
        p.get_by_role("button", name="O que este projeto traz de novo").click()
        dlg = p.get_by_role("dialog")
        dlg.get_by_text("nenhuma fonte disponível").wait_for()
        self.assertIn("Comprar créditos", dlg.inner_text())
        self.assertIn("seu trabalho fica salvo", dlg.inner_text().lower())
        dlg.get_by_role("button", name="Fechar").first.click()
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM ai_executions WHERE org_id = $1", osc.org_id), 0)
        self.assertEqual(p.errors, [])

    def test_pilot_credit_order_and_admin_approval_panel(self):
        osc = new_account("osc")
        p = self.page()
        self.login(p, osc)
        p.goto(self.base + "/ia")
        p.get_by_role("heading", name="Comprar créditos").wait_for()
        self.assertIn("Fase piloto", p.inner_text("main"))
        p.get_by_role("button", name="Fazer pedido").click()
        dlg = p.get_by_role("dialog")
        dlg.get_by_label("Li e aceito os termos de crédito").check()
        dlg.get_by_role("button", name="Confirmar pedido").click()
        p.get_by_text("piloto: aguardando a administração").wait_for()
        adm, secret = make_admin()
        q = self.page()
        q.goto(self.base + "/entrar")
        q.get_by_label("E-mail").fill(adm.email)
        q.get_by_label("Senha").fill(PASSWORD)
        q.get_by_role("button", name="Entrar").click()
        from tests.support import fresh_totp
        q.get_by_label("Código do aplicativo autenticador").fill(fresh_totp(secret))
        q.get_by_role("button", name="Confirmar").click()
        q.get_by_role("heading", name=re.compile("Olá|Visão geral")).wait_for()
        q.goto(self.base + "/admin/ia/financeiro")
        q.get_by_role("heading", name="Pedidos de crédito").wait_for()
        q.get_by_role("button", name="Aprovar como concessão de piloto").first.wait_for()
        txt = q.inner_text("main")
        self.assertIn("NÃO MEDIDO", txt)
        self.assertIn("piloto", txt)
        q.get_by_role("button", name="Aprovar como concessão de piloto").first.click()
        q.get_by_role("dialog").get_by_role("textbox").fill("Piloto de medição de custo.")
        q.get_by_role("dialog").get_by_role("button", name="Confirmar").click()
        # billing.write é operação sensível: o step-up pede senha + código; a confirmação vale 15 minutos
        su = q.get_by_role("dialog").filter(has_text="Confirme sua identidade")
        su.wait_for()
        su.get_by_label("Senha").fill(PASSWORD)
        su.get_by_label("Código do aplicativo autenticador").fill(fresh_totp(secret))
        su.get_by_role("button", name="Confirmar").click()
        q.get_by_text("Concessão de piloto registrada").wait_for()
        p.reload()
        p.get_by_role("heading", name="Extrato de créditos").wait_for()
        self.assertIn("creditado", p.inner_text("main"))
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT ai_credit_balance_bucket($1,'purchased')", osc.org_id), 0, "piloto nunca vira compra")
            self.assertEqual(d.scalar("SELECT ai_credit_balance_bucket($1,'promotional')", osc.org_id), 70 + 100)
        self.assertEqual(p.errors + q.errors, [])
