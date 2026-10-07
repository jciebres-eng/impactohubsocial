"""Gate 8 do pacote de execução: os dois itens de frente que não tinham teste.

O QUE JÁ ESTAVA COBERTO

`test_e2e_v0181_accessibility.py` confere no NAVEGADOR, com estilo computado: nome acessível de todo
controle, erro anunciado a tecnologia assistiva, link de pular, navegação só por teclado, foco
visível, marcos e um único H1, alternativa textual, contraste WCAG AA em tema claro e escuro,
ausência de rolagem horizontal em 390px, tamanho de alvo de toque e movimento reduzido. São 13
conferências, e `ACCESSIBILITY_REPORT.md` declara 6 pendências com nome e motivo (axe, leitor de tela
real, segundo navegador, zoom a 200%, simulação de visão, navegação por voz).

O QUE FALTAVA, E ESTÁ AQUI

A lista do pacote nomeia **modal** e **tabelas**, e nenhum dos dois tinha teste.

*Modal* é o lugar onde acessibilidade costuma quebrar: foco que não entra, Escape que não fecha, foco
que não volta para quem abriu, e o resto da página continuando alcançável por trás. O componente usa
`<dialog>` nativo com `showModal()`, que resolve os quatro no navegador — mas "resolve por construção"
é hipótese até alguém medir, e é o que estes testes fazem.

*Tabelas*: ver `EveryTableHeaderIsUnambiguousTests` abaixo, onde o achado inicial (411 `<th>` sem
`scope`) não resistiu à conferência.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from tests.support import PASSWORD, ROOT, new_account, server

try:
    from playwright.sync_api import sync_playwright
    HAVE_PW = True
except ImportError:  # pragma: no cover
    HAVE_PW = False


@unittest.skipUnless(HAVE_PW, "playwright ausente")
class TheModalTrapsFocusAndGivesItBackTests(unittest.TestCase):
    """As quatro quebras clássicas de modal, medidas no navegador."""

    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        cls._old = cls.state.settings.public_base_url
        cls.state.settings.public_base_url = cls.base
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.conta = new_account("osc", compliance="approved")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.state.settings.public_base_url = cls._old

    def _abre_modal(self):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        p = ctx.new_page()
        p.errors = []
        p.on("pageerror", lambda e: p.errors.append(str(e)))
        p.goto(self.base + "/entrar")
        p.get_by_label("E-mail").fill(self.conta.email)
        p.get_by_label("Senha").fill(PASSWORD)
        p.get_by_role("button", name="Entrar").click()
        p.get_by_role("heading", name=re.compile("Olá")).wait_for(timeout=15000)
        p.goto(self.base + "/ideias")
        gatilho = p.get_by_role("button", name="Anotar ideia")
        gatilho.wait_for(timeout=15000)
        gatilho.click()
        p.locator("dialog[open]").wait_for(timeout=10000)
        return p

    def test_the_modal_announces_itself_with_a_name(self):
        p = self._abre_modal()
        self.addCleanup(p.context.close)
        rotulo = p.evaluate("""() => {
            const d = document.querySelector('dialog[open]');
            if (!d) return null;
            const por = d.getAttribute('aria-labelledby');
            const alvo = por ? document.getElementById(por) : null;
            return {rotulado_por: por, texto: alvo ? alvo.textContent.trim() : null,
                    aria_label: d.getAttribute('aria-label')};
        }""")
        self.assertIsNotNone(rotulo, "nenhum <dialog open> na página")
        self.assertTrue(rotulo["texto"] or rotulo["aria_label"],
                        f"modal sem nome acessível: {rotulo}")
        self.assertEqual(p.errors, [])

    def test_the_focus_moves_into_the_modal_when_it_opens(self):
        p = self._abre_modal()
        self.addCleanup(p.context.close)
        dentro = p.evaluate("""() => {
            const d = document.querySelector('dialog[open]');
            return !!(d && document.activeElement && d.contains(document.activeElement));
        }""")
        self.assertTrue(dentro, "o foco ficou fora do modal depois de abrir")

    def test_the_rest_of_the_page_is_inert_behind_the_modal(self):
        """`showModal()` torna o resto da página inerte. Sem isso, o teclado passeia por trás do
        modal e quem usa leitor de tela lê a página de baixo como se o modal não existisse."""
        p = self._abre_modal()
        self.addCleanup(p.context.close)
        inerte = p.evaluate("""() => {
            const d = document.querySelector('dialog[open]');
            // Um botão FORA do modal não pode receber foco enquanto ele está aberto.
            const fora = [...document.querySelectorAll('button, a[href], input')]
                .filter(el => !d.contains(el) && el.offsetParent !== null);
            if (!fora.length) return {testado: 0, focou: false};
            fora[0].focus();
            return {testado: fora.length, focou: d.contains(document.activeElement) === false
                                                 && document.activeElement === fora[0]};
        }""")
        self.assertGreater(inerte["testado"], 0, "nenhum elemento fora do modal para testar")
        self.assertFalse(inerte["focou"],
                         "elemento atrás do modal recebeu foco: a página não ficou inerte")

    def test_escape_closes_the_modal_and_the_focus_comes_back(self):
        p = self._abre_modal()
        self.addCleanup(p.context.close)
        p.keyboard.press("Escape")
        p.wait_for_timeout(300)
        self.assertEqual(p.locator("dialog[open]").count(), 0, "Escape não fechou o modal")
        voltou = p.evaluate("""() => {
            const a = document.activeElement;
            return !!a && a.tagName !== 'BODY';
        }""")
        self.assertTrue(voltou, "depois de fechar, o foco foi para <body>: quem navega por teclado "
                                "perde o lugar e recomeça do topo da página")
        self.assertEqual(p.errors, [])


class EveryTableHeaderIsUnambiguousTests(unittest.TestCase):
    """O achado que não resistiu à conferência, e a trava do caso que importa de verdade.

    A primeira medição acusou **411 `<th>` sem `scope`** e parecia um defeito sério de
    acessibilidade. Dois erros de instrumento depois, o número real é outro:

    * o padrão `<th[^>]*>` casa com `<thead>` também, porque `<th` é prefixo de `<thead`;
    * e `<th>` sem `scope` DENTRO de `<thead>` não é ambíguo: a inferência de cabeçalho do HTML
      associa a coluna de forma confiável, e leitor de tela nenhum se perde ali.

    Contagem correta: 4 com `scope` explícito, 16 `<th />` vazios (coluna de ações), 318 sem `scope`
    dentro de `<thead>`, e **zero** ambíguos. Não havia defeito.

    O que havia era a ausência da trava para o caso que importa: um `<th>` de CABEÇALHO DE LINHA,
    fora de `<thead>`, sem `scope="row"`. Esse é ambíguo de verdade — o leitor não tem como saber se
    o cabeçalho governa a linha ou a coluna. Este teste permite os 318 e recusa o primeiro ambíguo
    que aparecer. Reescrever 318 marcações por estética seria risco de regressão sem ganho; travar o
    caso ambíguo custa este arquivo.
    """

    TH = re.compile(r"<th(?=[\s>/])([^>]*?)>")

    def _varre(self) -> tuple[int, int, int, list[str]]:
        com_scope = vazios = em_thead = 0
        ambiguos: list[str] = []
        for f in sorted((ROOT / "web" / "src").rglob("*.tsx")):
            texto = f.read_text(encoding="utf-8")
            for m in self.TH.finditer(texto):
                atributos = m.group(1)
                if "scope=" in atributos:
                    com_scope += 1
                    continue
                if atributos.strip() == "/":
                    vazios += 1
                    continue
                antes = texto[max(0, m.start() - 400):m.start()]
                ultimo = antes.rfind("<thead")
                if ultimo != -1 and "</thead" not in antes[ultimo:]:
                    em_thead += 1
                else:
                    linha = texto[:m.start()].count("\n") + 1
                    ambiguos.append(f"{f.name}:{linha} {m.group(0)[:70]}")
        return com_scope, vazios, em_thead, ambiguos

    def test_no_header_cell_is_ambiguous_about_what_it_heads(self):
        com_scope, vazios, em_thead, ambiguos = self._varre()
        self.assertEqual(ambiguos, [],
                         "cabeçalho de tabela fora de <thead> e sem scope: o leitor de tela não tem "
                         f"como saber se governa a linha ou a coluna. {ambiguos}")
        # A varredura precisa estar MEDINDO algo: zero em tudo significaria regex quebrada.
        self.assertGreater(com_scope + em_thead, 100,
                           "a varredura não encontrou cabeçalhos: o padrão deve ter quebrado")

    def test_the_scan_does_not_mistake_thead_for_th(self):
        """Controle do instrumento: `<thead>` não pode ser contado como célula de cabeçalho."""
        self.assertIsNone(self.TH.match("<thead>"), "o padrão casa <thead> e inflaria a contagem")
        self.assertIsNotNone(self.TH.match("<th>"))
        self.assertIsNotNone(self.TH.match('<th scope="row">'))
        self.assertIsNotNone(self.TH.match("<th />"))


class TheOfflineTypecheckSaysWhatItCanAndCannotCheckTests(unittest.TestCase):
    """O escopo do typecheck offline, MEDIDO e não presumido.

    `tsconfig.offline.json` existe porque `@types/react` não é instalável aqui (D-SUP1). Ele herda
    `strict: true` e `noUnusedLocals` de `tsconfig.json` e acrescenta `noImplicitAny`. Mas herdar
    `strict` não diz o que ele realmente pega — os stubs mínimos em `web/types/` decidem isso, e a
    diferença foi medida plantando erro de cada tipo:

      erro de lógica / hook      `setNome(42)` em estado string   → PEGA   (TS2345)
      prop de componente tipada  `variant="roxo"`                 → PEGA   (TS2322)
      atributo de elemento DOM   `<a href={42}>`                  → NÃO pega

    O terceiro é limitação declarada do stub: `JSX.IntrinsicElements` é `[tag: string]: any`. Escrever
    "typecheck passa" sem dizer isso seria afirmar uma cobertura que não existe.
    """

    def test_the_offline_config_inherits_strict_and_adds_no_implicit_any(self):
        import json
        bruto = (ROOT / "web" / "tsconfig.offline.json").read_text(encoding="utf-8")
        offline = json.loads(re.sub(r"^\s*//.*$", "", bruto, flags=re.M))
        base = json.loads((ROOT / "web" / "tsconfig.json").read_text(encoding="utf-8"))
        self.assertEqual(offline["extends"], "./tsconfig.json")
        self.assertTrue(base["compilerOptions"]["strict"], "a base deixou de ser estrita")
        self.assertTrue(base["compilerOptions"]["noUnusedLocals"])
        self.assertTrue(offline["compilerOptions"]["noImplicitAny"])

    def test_the_stub_limitation_is_written_down_where_someone_will_read_it(self):
        stub = (ROOT / "web" / "types" / "react" / "index.d.ts").read_text(encoding="utf-8")
        self.assertIn("IntrinsicElements", stub)
        # A limitação tem de estar declarada em BLOCKERS.md, não só no comentário do stub.
        bloqueios = (ROOT / "docs" / "execution" / "BLOCKERS.md").read_text(encoding="utf-8")
        self.assertIn("D-SUP1", bloqueios)
        self.assertIn("tsconfig.offline.json", bloqueios)

    def test_the_stub_files_exist_where_the_config_points(self):
        for caminho in ("types/react/index.d.ts", "types/react/jsx-runtime.d.ts",
                        "types/react-dom/client.d.ts"):
            with self.subTest(caminho):
                self.assertTrue((ROOT / "web" / caminho).exists(),
                                f"{caminho} não existe e o typecheck offline não roda")

    def test_the_build_output_is_present_and_fresh_enough_to_be_the_tested_one(self):
        """O E2E de navegador serve `web/dist`. Se o `dist` for de um código anterior, os testes de
        frente medem uma aplicação que não é a que está sendo entregue."""
        dist = ROOT / "web" / "dist"
        self.assertTrue((dist / "index.html").exists(), "web/dist/index.html ausente")
        info = pathlib.Path(dist / "build-info.json")
        self.assertTrue(info.exists(), "build-info.json ausente: não dá para saber o que foi servido")
        import json
        dados = json.loads(info.read_text(encoding="utf-8"))
        for chave in ("version", "built_at", "js", "css"):
            self.assertIn(chave, dados)
        self.assertTrue((dist / dados["js"]).exists(), f"{dados['js']} declarado e ausente")
        self.assertTrue((dist / dados["css"]).exists(), f"{dados['css']} declarado e ausente")


class TheInstalledTreeInventoryMatchesWhatIsOnDiskTests(unittest.TestCase):
    """O inventário da árvore instalada não pode virar fotografia (ressalva 8 do adendo).

    `web/INSTALLED_TREE.json` responde *"o build entregue veio de quais bytes?"*. Ele NÃO é um
    `package-lock.json`, e o teste existe para que ninguém o confunda com um: confere que o arquivo
    declara o que é, que os ausentes estão nomeados, e que o sha256 de cada pacote bate com o disco.
    """

    @classmethod
    def setUpClass(cls):
        cls.inventario = ROOT / "web" / "INSTALLED_TREE.json"
        cls.nm = ROOT / "web" / "node_modules"

    def test_the_inventory_declares_that_it_is_not_a_lockfile(self):
        import json
        d = json.loads(self.inventario.read_text(encoding="utf-8"))
        self.assertIn("package-lock", d["o_que_este_arquivo_nao_e"],
                      "o inventário não diz que NÃO é um lockfile; alguém vai confundir")
        self.assertIn("D-SUP1", d["o_que_este_arquivo_nao_e"])
        self.assertTrue(d["declarados_e_ausentes"],
                        "nenhum ausente declarado: ou o 403 caiu (e o lockfile real é possível), "
                        "ou o inventário parou de olhar")
        self.assertTrue(d["motivo_das_ausencias"])

    @unittest.skipUnless((ROOT / "web" / "node_modules").is_dir(),
                         "node_modules ausente: o inventário não é conferível neste ambiente")
    def test_regenerating_the_inventory_reproduces_what_is_committed(self):
        import pathlib
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saida = pathlib.Path(tmp) / "i.json"
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "web_installed_tree.py"),
                                str(saida)], capture_output=True, text=True, cwd=ROOT, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            self.assertEqual(saida.read_text(encoding="utf-8"),
                             self.inventario.read_text(encoding="utf-8"),
                             "INSTALLED_TREE.json divergiu do disco. Regere com: "
                             "python3 scripts/web_installed_tree.py")

    def test_the_build_critical_packages_are_all_present(self):
        """Os ausentes podem ser de tipagem ou de mobile. Não podem ser do que o build usa."""
        import json
        d = json.loads(self.inventario.read_text(encoding="utf-8"))
        instalados = {p["name"] for p in d["pacotes"]}
        for pacote in ("react", "react-dom", "scheduler", "esbuild", "typescript"):
            with self.subTest(pacote):
                self.assertIn(pacote, instalados,
                              f"{pacote} é usado pelo build e não está na árvore instalada")
