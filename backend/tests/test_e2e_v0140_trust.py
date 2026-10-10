"""E2E de navegador da camada de confiança: verificação PÚBLICA (sem login), tema claro/escuro, assinatura em duas
camadas pela interface e campanha pública com cotas. Pulado se Playwright ou o build do frontend faltarem."""
import re
import unittest

from tests.support import PASSWORD, ROOT, last_signature_code, new_account, server

DIST = ROOT / "web" / "dist" / "index.html"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")

def _publish_campaign(osc, campaign_id: str) -> None:
    """v0.33.0 (ADR-374): publicar exige envio para revisão, aprovação por outra pessoa da equipe e beneficiário
    verificado. O atalho `PATCH status=published` responde 409 de propósito; os testes antigos passam por aqui."""
    from tests.support import make_staff, reauth, verify_beneficiary
    rev = make_staff("compliance")
    # v0.35.0: compliance.write exige identidade confirmada há menos de 15 min (step-up); quem começa a trabalhar confirma
    reauth(rev)
    assert osc.post(f"/v1/campaigns/{campaign_id}/submit").status == 200
    r = rev.post(f"/v1/admin/donation-campaigns/{campaign_id}/review", {"approve": True, "note": "Revisão de teste: finalidade clara."})
    assert r.status == 200, r
    verify_beneficiary(osc.org_id, rev)   # v0.35.0: decisão + confirmação por outra pessoa (KYC-03)
    r = osc.post(f"/v1/campaigns/{campaign_id}/publish")
    assert r.status == 200, r

class TrustE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        cls._old = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.osc = new_account("osc", compliance="approved")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old

    def page(self, **ctx_kwargs):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900}, **ctx_kwargs)
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

    def _signed_record(self):
        r = self.osc.upload("/v1/documents", filename="relatorio-e2e.txt", content=b"Relatorio final para verificar",
                            fields={"doc_type": "relatorio", "title": "Relatório final E2E"})
        doc = r.json["id"]
        self.osc.post("/v1/signatures/challenge", {"subject_type": "document", "subject_id": doc})
        code = last_signature_code(self.osc.email)
        self.osc.post("/v1/signatures", {"subject_type": "document", "subject_id": doc, "role": "legal_representative",
                                         "statement": "Assino o relatório final para a verificação pública.",
                                         "password": PASSWORD, "code": code})
        rec = self.osc.post("/v1/verifiable-records", {"subject_type": "document", "subject_id": doc})
        assert rec.status == 201, rec
        return doc, rec.json

    # ---------------------------------------------------------------- verificação pública, sem login
    def test_third_party_verifies_without_logging_in(self):
        doc, rec = self._signed_record()
        p = self.page()
        p.goto(self.base + "/verificar")
        p.get_by_role("heading", name="Verificação de documento").wait_for()
        p.get_by_label("Código de verificação").fill(rec["code"])
        p.get_by_role("button", name="Verificar").click()
        p.get_by_text("Integridade intacta").wait_for()
        body = p.inner_text("body")
        self.assertIn("Relatório final E2E", body)
        self.assertIn("Válido", body)
        self.assertIn("Representante legal", body)
        self.assertNotIn(self.osc.email, body)            # nenhum dado pessoal na página pública
        self.assertNotIn("Usuária osc", body)
        self.assertEqual(p.errors, [])

    def test_public_page_shows_revocation(self):
        doc, rec = self._signed_record()
        self.osc.post(f"/v1/verifiable-records/{rec['id']}/revoke",
                      {"reason": "Documento substituído por erro material na tabela de metas."})
        p = self.page()
        p.goto(f"{self.base}/verificar/{rec['code']}")
        p.get_by_text("REVOGADO").first.wait_for()
        self.assertIn("erro material", p.inner_text("body"))
        self.assertEqual(p.errors, [])

    def test_unknown_code_shows_friendly_error(self):
        p = self.page()
        p.goto(self.base + "/verificar/IMP-ZZZZ-ZZZZ-ZZZZ")
        p.get_by_text(re.compile("Não encontramos|não encontrado", re.I)).wait_for()
        self.assertEqual(p.errors, [])

    # ---------------------------------------------------------------- assinatura em duas camadas pela interface
    def test_two_layer_signature_through_the_ui(self):
        osc = new_account("osc", compliance="approved")
        d = osc.post("/v1/drafts", {"kind": "project_proposal", "title": "Proposta assinada na interface",
                                    "content": "Conteúdo da proposta."})
        self.assertEqual(d.status, 201, d)
        did = d.json["id"]
        rec = osc.post("/v1/verifiable-records", {"subject_type": "draft", "subject_id": did})
        self.assertEqual(rec.status, 201, rec)
        p = self.page()
        self.login(p, osc)
        p.goto(self.base + "/verificacoes")
        p.get_by_text(rec.json["code"]).wait_for()
        p.get_by_role("link", name="Abrir página").first.click()
        p.get_by_text("Integridade intacta").wait_for()
        self.assertEqual(p.errors, [])

    # ---------------------------------------------------------------- tema claro/escuro escolhido pela pessoa
    def test_theme_choice_is_applied_and_persists(self):
        osc = new_account("osc", compliance="approved")
        p = self.page()
        self.login(p, osc)
        p.goto(self.base + "/conta/preferencias")
        p.get_by_label("Tema").select_option("dark")
        self.assertEqual(p.evaluate("document.documentElement.getAttribute('data-theme')"), "dark")
        bg_dark = p.evaluate("getComputedStyle(document.body).backgroundColor")
        p.get_by_role("button", name="Salvar").click()
        p.wait_for_timeout(400)
        p.reload()                                        # aplicado antes do primeiro render, sem piscar
        p.get_by_label("Tema").wait_for()
        self.assertEqual(p.evaluate("document.documentElement.getAttribute('data-theme')"), "dark")
        self.assertEqual(p.evaluate("getComputedStyle(document.body).backgroundColor"), bg_dark)
        p.get_by_label("Tema").select_option("light")
        self.assertNotEqual(p.evaluate("getComputedStyle(document.body).backgroundColor"), bg_dark)
        self.assertEqual(p.errors, [])

    def test_dark_theme_keeps_readable_contrast(self):
        osc = new_account("osc", compliance="approved")
        p = self.page()
        self.login(p, osc)
        p.goto(self.base + "/conta/preferencias")
        p.get_by_label("Tema").select_option("dark")
        ratio = p.evaluate("""() => {
          const lum = (c) => { const [r,g,b] = c.match(/\\d+/g).map(Number).map(v => v/255)
            .map(v => v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4));
            return 0.2126*r + 0.7152*g + 0.0722*b; };
          const el = document.querySelector('.muted') || document.body;
          const a = lum(getComputedStyle(el).color), b = lum(getComputedStyle(document.body).backgroundColor);
          const hi = Math.max(a,b), lo = Math.min(a,b);
          return (hi + 0.05) / (lo + 0.05);
        }""")
        self.assertGreaterEqual(ratio, 4.5, f"contraste do texto secundário no tema escuro: {ratio:.2f}:1")

    # ---------------------------------------------------------------- campanha pública com cotas
    def test_public_campaign_shows_remaining_quotas(self):
        osc = new_account("osc", compliance="approved")
        funder = new_account("company", compliance="approved")
        pid = osc.post("/v1/projects", {"title": "Projeto da campanha E2E", "summary": "Resumo do projeto da campanha.",
                                        "causes": ["educacao"], "territory": "MT"}).json["id"]
        q = osc.post("/v1/funding-quotas", {"project_id": pid, "label": "Cota de apoio", "quota_cents": 30000,
                                             "total_quotas": 10}).json["id"]
        osc.patch(f"/v1/funding-quotas/{q}", {"status": "open"})
        funder.post(f"/v1/funding-quotas/{q}/pledges", {"quantity": 4})
        slug = f"campanha-e2e-{pid[:8]}"
        c = osc.post("/v1/campaigns", {"project_id": pid, "slug": slug, "title": "Ajude o projeto da campanha",
                                        "summary": "Precisamos de apoio para concluir as atividades deste ano.",
                                        "purpose": "Atividades deste ano.", "contingency_policy": "Sem a meta, o valor vai para as atividades.",
                                        "refund_policy": "Estorno pelo provedor."}).json
        _publish_campaign(osc, c["id"])   # v0.33.0 (ADR-374): quatro olhos + beneficiário verificado
        p = self.page()
        p.goto(f"{self.base}/campanha/{slug}")
        p.get_by_role("heading", name="Faltam 6 cota(s)").wait_for()
        body = p.inner_text("body")
        self.assertIn("Ajude o projeto da campanha", body)
        self.assertIn("R$", body)
        self.assertEqual(p.errors, [])

    # ---------------------------------------------------------------- acessibilidade básica das telas novas
    def test_new_pages_have_no_console_errors_and_one_h1(self):
        osc = new_account("osc", compliance="approved")
        p = self.page()
        self.login(p, osc)
        for path in ("/identidade", "/verificacoes", "/acordos", "/acordos/novo", "/cotas", "/campanha-gestao",
                     "/conta/preferencias"):
            p.goto(self.base + path)
            p.wait_for_timeout(250)
            h1 = p.locator("h1").count()
            self.assertEqual(h1, 1, f"{path}: esperado 1 <h1>, achei {h1}")
            self.assertEqual(p.evaluate("document.documentElement.lang"), "pt-BR", path)
            dup = p.evaluate("""() => { const seen = {}, bad = [];
              document.querySelectorAll('[id]').forEach(e => { if (seen[e.id]) bad.push(e.id); seen[e.id] = 1; });
              return bad; }""")
            self.assertEqual(dup, [], f"{path}: IDs duplicados {dup}")
        self.assertEqual(p.errors, [])
