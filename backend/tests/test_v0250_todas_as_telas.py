"""v0.25.0 — TODAS as 218 telas do roteador abertas no navegador, com cada perfil de demonstração.

A prova anterior (`test_v0240_demo_completa`) abria só as telas do MENU de cada perfil. Este teste
abre as 218, inclusive as 119 que só se alcançam por link e as 52 que dependem de um registro: para
essas, usa um registro REAL da demonstração, buscado no banco. Também confere a RECUSA: cada tela
restrita é aberta por um perfil que não deve vê-la, e o esperado é a mensagem de área indisponível,
não um erro.

Grava `docs/execution/ROUTE_RUNTIME_MATRIX.csv` (uma linha por visita) e
`docs/evidence/telas_v0250/resumo.json`. Falha com a lista de cada visita que não deu certo.
Sem Playwright/Chromium ou sem o build do front, é PULADO e diz por quê.
"""
from __future__ import annotations

import csv
import json
import os
import re
import unittest
from collections import Counter

from tests.support import PASSWORD, ROOT, server
from tests import screen_crawler as robo

DIST = ROOT / "web" / "dist" / "index.html"
MATRIZ = ROOT / "docs" / "execution" / "ROUTE_RUNTIME_MATRIX.csv"
EVID = ROOT / "docs" / "evidence" / "telas_v0250"
try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False

SUCESSO = {robo.OK, robo.VAZIA, robo.RECUSA_CERTA}


def popular_demonstracao(base: str, state) -> None:
    """Dados de demonstração: o seed, mais as jornadas que criam registros pelo próprio produto."""
    os.environ["DEMO_PASSWORD"] = PASSWORD
    from impacto import seed_dev
    r = seed_dev.seed(state)
    assert r["status"] in ("seeded", "already_seeded"), r
    try:
        from tests import demo_journeys
    except ImportError:  # as jornadas chegam numa etapa seguinte
        return
    demo_journeys.run(base, state)


@unittest.skipUnless(HAVE_PW and DIST.exists(), "Playwright ou build do frontend indisponível")
class EveryScreenOpensForEveryPersonaTests(unittest.TestCase):
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
            enc = c.scalar("SELECT mfa_secret_enc FROM users WHERE email = $1", cls.emails["admin"])
        cls.segredo = cls.state.cipher.decrypt(enc)

    @classmethod
    def tearDownClass(cls):
        cls.state.settings.public_base_url = cls._old

    def _consulta(self, sql: str):
        from impacto.db.pool import DbContext
        with self.state.pool.tx(DbContext(system=True)) as c:
            return c.scalar(sql)

    def _totp(self) -> str:
        """Um código por login: a janela de 30 s não pode ser reutilizada (o servidor queima o código)."""
        from tests.support import fresh_totp
        return fresh_totp(self.segredo)

    def test_every_screen_in_the_router_opens_with_real_data(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                # TELAS_FILTRO (expressão regular) restringe as rotas — só para depurar; a contagem de 218
                # abaixo faz o teste falhar se alguém deixar o filtro ligado.
                filtro = os.getenv("TELAS_FILTRO")
                lista = [x for x in robo.inventario() if re.search(filtro, x["rota"])] if filtro else None
                linhas = robo.rodar(browser, self.base, PASSWORD, self.emails, self._consulta, self._totp, lista)
            finally:
                browser.close()
        MATRIZ.parent.mkdir(parents=True, exist_ok=True)
        campos = ["rota", "tabela", "componente", "alcance", "persona", "deve_ver", "url", "estado", "detalhe",
                  "chamadas_api", "api_4xx", "ms"]
        with MATRIZ.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            for x in linhas:
                w.writerow({**x, "api_4xx": " | ".join(x["api_4xx"])})
        estados = Counter(x["estado"] for x in linhas)
        rotas = {x["rota"] for x in linhas}
        rotas_ok = {x["rota"] for x in linhas if x["deve_ver"] and x["estado"] in (robo.OK, robo.VAZIA)}
        # Persona que não participa de nenhum registro daquele tipo (o governo não tem pagamento seu
        # na demonstração) fica registrada na matriz, mas não é falha DA TELA: a tela é provada por
        # quem tem o registro, e a regra abaixo exige que TODA rota seja aberta com sucesso por alguém.
        def nao_participa(x):
            return x["estado"] == "SEM_REGISTRO" and "não participa" in x["detalhe"]
        falhas = [x for x in linhas if x["estado"] not in SUCESSO and not nao_participa(x)]
        EVID.mkdir(parents=True, exist_ok=True)
        (EVID / "resumo.json").write_text(json.dumps({
            "visitas": len(linhas), "rotas": len(rotas), "rotas_abertas_com_sucesso": len(rotas_ok),
            "persona_sem_registro_proprio": sum(1 for x in linhas if nao_participa(x)),
            "estados": dict(estados.most_common()),
            "falhas": [{k: x[k] for k in ("rota", "persona", "url", "estado", "detalhe", "api_4xx")} for x in falhas],
        }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.assertEqual(len(rotas), 220, "o inventário mudou: regere screen_inventory.json")   # v0.26.0: +/torre +/torre-territorial
        self.assertEqual(sorted(rotas - rotas_ok), [], "rota que nenhum perfil conseguiu abrir com dado real")
        self.assertEqual(falhas, [], "\n" + "\n".join(
            f"{x['estado']:<16} {x['persona']:<10} {x['url'] or x['rota']}  {x['detalhe']}" for x in falhas))


@unittest.skipUnless(HAVE_PW, "Playwright indisponível")
class TheDeadButtonDetectorDetectsTests(unittest.TestCase):
    """Controle positivo: "zero botões sem ação" só vale se o detector acusa um botão morto quando há."""

    def test_a_button_without_handler_and_a_link_without_href_are_reported(self):
        html = ('<button>Morto</button><button id="b">Vivo</button><form><button>Enviar</button></form>'
                '<a>Link sem destino</a><a href="/x">Link bom</a>'
                '<script>document.getElementById("b")["__reactProps$t"] = {onClick: () => 1};</script>')
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                p = browser.new_page()
                p.set_content(html)
                achados = p.evaluate(robo.SEM_ACAO_JS)
            finally:
                browser.close()
        self.assertEqual(achados, ["botão: Morto", "link: Link sem destino"])


@unittest.skipUnless(HAVE_PW, "Playwright indisponível")
class TheAxeHookReportsViolationsTests(unittest.TestCase):
    """O axe-core real só é baixado no CI (o registro npm é bloqueado no ambiente de desenvolvimento).
    Aqui se prova a LIGAÇÃO: com um axe falso que devolve uma violação conhecida, o robô a relata no
    formato que o relatório espera — para que zero violações no CI não seja zero por fiação quebrada."""

    def test_the_axe_result_is_collected_in_the_expected_shape(self):
        falso = ("window.axe = {run: async (doc, opts) => ({violations: [{id: 'color-contrast', impact: 'serious',"
                 " help: 'Contraste', nodes: [{target: ['p.x']}, {target: ['p.y']}]}]})};")
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                p = browser.new_page()
                p.set_content("<p class='x'>a</p><p class='y'>b</p>")
                p.add_script_tag(content=falso)
                r = p.evaluate(robo.AXE_RUN_JS)
            finally:
                browser.close()
        self.assertEqual(r, [{"id": "color-contrast", "impact": "serious", "help": "Contraste", "nodes": 2, "exemplo": "p.x"}])
