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

    def _instalados_agora(self) -> dict[str, str]:
        import json
        fora = {}
        for pk in list(self.nm.glob("*/package.json")) + list(self.nm.glob("@*/*/package.json")):
            fora[str(pk.parent.relative_to(self.nm))] = json.loads(pk.read_text(encoding="utf-8")).get("version")
        return fora

    @unittest.skipUnless((ROOT / "web" / "node_modules").is_dir(),
                         "node_modules ausente: o inventário não é conferível neste ambiente")
    def test_every_recorded_package_that_is_installed_has_the_recorded_version(self):
        """Vale em QUALQUER ambiente: a versão de cada pacote registrado bate com o que está instalado.

        No CI do GitHub (v0.24.1), `npm ci` instala a árvore inteira do lockfile; a comparação do
        arquivo inteiro deixa de fazer sentido lá (a árvore é outra, maior), mas esta continua: os
        pacotes que produziram o build versionado têm de ser as mesmas versões que o CI instala.
        """
        import json
        registrados = {p["name"]: p["version"] for p in
                       json.loads(self.inventario.read_text(encoding="utf-8"))["pacotes"]}
        agora = self._instalados_agora()
        divergentes = {n: (v, agora[n]) for n, v in registrados.items() if n in agora and agora[n] != v}
        self.assertEqual(divergentes, {}, "pacote registrado no inventário com outra versão instalada")

    @unittest.skipUnless((ROOT / "web" / "node_modules").is_dir(),
                         "node_modules ausente: o inventário não é conferível neste ambiente")
    def test_regenerating_the_inventory_reproduces_what_is_committed(self):
        """Na máquina que produziu o build versionado (mesmo conjunto de pacotes), o arquivo inteiro —
        com o sha256 do conteúdo de cada pacote — tem de se reproduzir byte a byte.

        Em outro ambiente o conjunto é outro e o teste diz isso em vez de comparar: o CI instala tudo
        pelo lockfile, e scripts de instalação (o do esbuild, por exemplo) podem mudar o conteúdo do
        diretório entre duas instalações da mesma versão. Exigir o hash lá seria falso alarme.
        """
        import json
        import pathlib
        import subprocess
        import sys
        import tempfile
        registrados = {p["name"] for p in json.loads(self.inventario.read_text(encoding="utf-8"))["pacotes"]}
        if set(self._instalados_agora()) != registrados:
            self.skipTest("árvore instalada diferente da que produziu o build versionado (CI com npm ci?)")
        with tempfile.TemporaryDirectory() as tmp:
            saida = pathlib.Path(tmp) / "i.json"
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "web_installed_tree.py"),
                                str(saida)], capture_output=True, text=True, cwd=ROOT, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            self.assertEqual(saida.read_text(encoding="utf-8"),
                             self.inventario.read_text(encoding="utf-8"),
                             "INSTALLED_TREE.json divergiu do disco. Regere com: "
                             "python3 scripts/web_installed_tree.py")


class TheScreenInventoryLosesNoScreenTests(unittest.TestCase):
    """Inventário que perde tela em silêncio é pior que inventário nenhum.

    Quatro defeitos já fizeram o extrator perder tela sem emitir um único erro: ancorar o padrão no
    fim da linha (`app.tsx` tem linha com DUAS rotas, a segunda sumia); pegar o `[` do TIPO (`R[]`)
    em vez do da lista (zero telas); exigir que o terceiro elemento fosse uma lista (as 30 entradas
    de `HELP`, cujo terceiro elemento é `true`, ficavam fora); e procurar o primeiro `=` depois de
    `const`, que em `[string, () => ReactNode][]` é o `=` de `=>` (as 9 de `PUBLIC`, fora).

    E a primeira versão DESTE teste conferia a contagem contra o bloco `ROUTES` — o mesmo recorte que
    o extrator lia —, então passava com 179 de 218. Um instrumento que se confere contra o próprio
    recorte não confere nada. Agora a conferência varre a região inteira das rotas com um método que
    não é o do extrator: todo `["/…"` entre `const ROUTES` e `const NAV`, qualquer que seja a tabela.
    """

    @classmethod
    def setUpClass(cls):
        import json
        cls.inv = json.loads((ROOT / "docs" / "execution" / "screen_inventory.json")
                             .read_text(encoding="utf-8"))
        cls.app = (ROOT / "web" / "src" / "app.tsx").read_text(encoding="utf-8")

    def _caminhos_declarados(self) -> set[str]:
        regiao = self.app[self.app.index("const ROUTES"):self.app.index("const NAV")]
        return set(re.findall(r'\["(/[^"]*)"\s*,', regiao))

    def test_every_route_the_router_declares_is_in_the_inventory(self):
        declarados = self._caminhos_declarados()
        inventariados = {t["rota"] for t in self.inv["lista"]}
        self.assertEqual(declarados - inventariados, set(),
                         "telas declaradas no roteador e ausentes do inventário")
        self.assertEqual(inventariados - declarados, set(),
                         "telas no inventário que o roteador não declara: o extrator inventou")

    def test_all_three_route_tables_are_represented(self):
        """`PUBLIC` e `HELP` já ficaram fora inteiras. Contar o total não pega isso: 179 parece muito."""
        por_tabela = self.inv["por_tabela"]
        for tabela in ("PUBLIC", "HELP", "ROUTES"):
            self.assertGreater(por_tabela.get(tabela, 0), 0, f"tabela {tabela} ausente do inventário")
        self.assertEqual(sum(por_tabela.values()), len(self.inv["lista"]))

    def test_no_screen_is_shadowed_by_an_earlier_table(self):
        """O roteador casa PUBLIC, depois HELP, depois ROUTES: padrão repetido antes torna a tela morta."""
        self.assertEqual(self.inv["sombreadas"], [],
                         "tela que o roteador nunca alcança porque uma tabela anterior casa primeiro")

    def test_the_inventory_is_not_trivially_small(self):
        """Contraprova dos defeitos anteriores: 0, 178 e 179 telas passariam todos despercebidos."""
        self.assertGreater(len(self.inv["lista"]), 200,
                           f"só {len(self.inv['lista'])} telas: o extrator deve ter quebrado")

    def test_regenerating_the_inventory_reproduces_what_is_committed(self):
        import json
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saida = pathlib.Path(tmp) / "i.json"
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_screen_inventory.py"),
                                str(saida)], capture_output=True, text=True, cwd=ROOT, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr[-1200:])
            self.assertEqual(json.loads(saida.read_text(encoding="utf-8")), self.inv,
                             "screen_inventory.json divergiu de app.tsx. Regere com: "
                             "python3 scripts/make_screen_inventory.py")


class TheScreenBackendMapTellsTheTruthAboutCoverageTests(unittest.TestCase):
    """O cruzamento tela × backend é acusação séria: tem que estar certo antes de ser publicado.

    Quatro números deste cruzamento já estiveram errados por defeito do extrator, não do produto:

      569 "operações sem interface"  → o front faz quase todo GET por `useLoad(caminho)`, e o
                                        extrator só enxergava `api.<verbo>(`.
      7   "telas sem backend"        → 1 era template aninhado (``…${pid ? `?x=${pid}` : ""}``) que
                                        a expressão regular cortava na crase de dentro, e 5 eram
                                        `${mode}` interpolando um literal registrado no backend.

    Sobrou UMA, e ela é de verdade: `/entrar` chama `GET /v1/meta/config`, que o backend não registra
    (só existe `GET /v1/meta/platform-status`). A chamada está dentro de um `.catch(() => {})`, então
    falha calada e o botão de SSO simplesmente nunca aparece.

    Este teste trava esse número. Se alguém corrigir a chamada, ele FALHA — de propósito: corrigir o
    produto deve exigir atualizar o que foi dito publicamente sobre ele.
    """

    #: Divergências conhecidas: nenhuma. A v0.23.1 anunciou UMA — `/entrar` → `GET /v1/meta/config`,
    #: "chamada desde a v0.10.0 sem rota por trás" — e estava ERRADA: a rota sempre existiu, como
    #: `Route` crua em `app.py` (`_infra_routes`), fora do registro `@route` que o cruzamento lia.
    #: O instrumento ignorava seis rotas e acusou o produto. Corrigido em
    #: `scripts/make_screen_backend_map.py`, que agora lê as duas fontes. Vazio aqui é afirmação
    #: forte: nenhuma tela chama operação que o backend não serve.
    AUSENTES: dict = {}

    @classmethod
    def setUpClass(cls):
        import json
        cls.mapa = json.loads((ROOT / "docs" / "execution" / "screen_backend_map.json")
                              .read_text(encoding="utf-8"))

    def test_the_only_missing_endpoint_is_the_one_we_declared(self):
        self.assertEqual(self.mapa["interface_sem_backend"], self.AUSENTES,
                         "mudou a lista de telas que chamam endpoint inexistente — atualize o que o"
                         " relatório afirma antes de mexer no teste")

    def test_the_map_covers_every_screen_in_the_inventory(self):
        import json
        inv = json.loads((ROOT / "docs" / "execution" / "screen_inventory.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual({t["rota"] for t in self.mapa["lista"]}, {t["rota"] for t in inv["lista"]})
        self.assertEqual(self.mapa["operacoes_no_backend"], 895 + 6)   # v0.27.0: 895 operações registradas (ADR-341; torre master e cartões do dia)

    def test_most_screens_resolve_to_a_registered_operation(self):
        """Contraprova do defeito do `useLoad`: com ele fora, só 138 das 218 'chamavam o backend'."""
        self.assertGreater(self.mapa["estados"]["backend presente"], 150,
                           "cobertura caiu: ou o front mudou, ou o extrator parou de ver um envoltório")

    def test_the_limits_of_the_method_are_written_in_the_script(self):
        """Quem ler o número precisa ler o que ele não prova, no mesmo arquivo que o produz."""
        fonte = (ROOT / "scripts" / "make_screen_backend_map.py").read_text(encoding="utf-8")
        for frase in ("quer dizer que a tela funciona", "O LIMITE DESTE MÉTODO",
                      "não chama diretamente"):
            self.assertIn(frase, fonte, f"sumiu do script a ressalva: {frase!r}")

    def test_regenerating_the_map_reproduces_what_is_committed(self):
        import json
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            saida = pathlib.Path(tmp) / "m.json"
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_screen_backend_map.py"),
                                str(saida)], capture_output=True, text=True, cwd=ROOT, timeout=180)
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            self.assertEqual(json.loads(saida.read_text(encoding="utf-8")), self.mapa,
                             "screen_backend_map.json divergiu. Regere com: "
                             "python3 scripts/make_screen_backend_map.py")


class TheWrittenDocsQuoteTheGeneratedNumbersTests(unittest.TestCase):
    """Documento que cita número gerado e não é conferido envelhece calado.

    `DEMO.md`, `TESTER_GUIDE.md` e `TROUBLESHOOTING.md` afirmam quantidades que saem do inventário e
    do cruzamento com o backend. Quando o roteador mudar, os três passam a mentir sem que nada
    reclame — e quem lê não tem como saber. Este teste quebra nessa hora.

    Já serviu uma vez: os dois guias diziam "35 telas só de Administração" e o inventário dizia 37.
    """

    @classmethod
    def setUpClass(cls):
        import json
        cls.inv = json.loads((ROOT / "docs" / "execution" / "screen_inventory.json")
                             .read_text(encoding="utf-8"))
        cls.mapa = json.loads((ROOT / "docs" / "execution" / "screen_backend_map.json")
                              .read_text(encoding="utf-8"))
        cls.textos = {n: (ROOT / "docs" / f"{n}.md").read_text(encoding="utf-8")
                      for n in ("DEMO", "TESTER_GUIDE", "TROUBLESHOOTING")}

    def _numeros(self) -> dict[str, int]:
        so_admin = sum(1 for t in self.inv["lista"] if t["alcanca"] == ["Administração"])
        return {
            "telas": self.inv["telas"],
            "sem menu": self.inv["so_por_link_direto"],
            "com parâmetro": self.inv["com_parametro"],
            "só Administração": so_admin,
            "sem chamada direta": self.mapa["estados"]["sem chamada direta"],
            "órfãs do backend": self.mapa["operacoes_que_nenhuma_tela_chama"],
        }

    def test_the_three_docs_exist_and_are_substantial(self):
        for nome, texto in self.textos.items():
            self.assertGreater(len(texto), 2000, f"{nome}.md é curto demais para servir a alguém")

    def test_every_number_the_docs_quote_matches_what_is_generated(self):
        n = self._numeros()
        # A âncora é só o texto ao redor; o número vem do JSON gerado, nunca escrito aqui.
        esperado = {
            "DEMO": [(n["telas"], "telas** servidas pelo roteador"),
                     (n["sem menu"], f"das {n['telas']} telas não estão em menu nenhum")],
            "TESTER_GUIDE": [(n["telas"], "telas** que o roteador serve"),
                             (n["sem menu"], "telas não estão em menu nenhum"),
                             (n["com parâmetro"], "telas exigem um registro existente"),
                             (n["só Administração"], "telas só existem para Administração"),
                             (n["sem chamada direta"], "telas): o componente não chama"),
                             (n["órfãs do backend"], "operações de API não têm tela")],
            "TROUBLESHOOTING": [(n["só Administração"], "telas são só de Administração"),
                                (n["sem chamada direta"], "telas): o componente não chama")],
        }
        for doc, pares in esperado.items():
            for valor, ancora in pares:
                self.assertIn(f"{valor} {ancora}", self.textos[doc],
                              f"{doc}.md não diz '{valor} {ancora}' — o número gerado mudou, o texto não")

    def test_the_known_broken_endpoint_is_named_in_both_guides(self):
        """Defeito conhecido escondido do testador faz ele gastar o dia a redescobri-lo."""
        for doc in ("TESTER_GUIDE", "TROUBLESHOOTING"):
            self.assertIn("/v1/meta/config", self.textos[doc])

    def test_no_doc_claims_the_system_cannot_be_broken_into(self):
        """Regra que está acima das outras: nenhum sistema ligado à internet recebe essa garantia."""
        for nome, texto in self.textos.items():
            baixo = texto.lower()
            for frase in ("impossível de invadir", "inviolável", "100% seguro", "à prova de invasão"):
                if frase in baixo:
                    # A menção é permitida só quando o texto a está NEGANDO.
                    self.assertIn("não", baixo[max(0, baixo.index(frase) - 120):baixo.index(frase)],
                                  f"{nome}.md afirma {frase!r}")


class TheLockfileAgreesWithThePackageAndTheInstalledTreeTests(unittest.TestCase):
    """v0.24.0 — `web/package-lock.json` chegou de fora (gerado com rede por outro agente). O que dá
    para conferir sem registro é conferido aqui; `npm ci` continua sendo da sessão com rede (D-SUP1).
    """

    @classmethod
    def setUpClass(cls):
        import json
        cls.lock = json.loads((ROOT / "web" / "package-lock.json").read_text(encoding="utf-8"))
        cls.pkg = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))

    def test_the_lockfile_declares_the_same_dependencies_as_package_json(self):
        raiz = self.lock["packages"][""]
        self.assertEqual(self.lock["lockfileVersion"], 3)
        self.assertEqual(raiz.get("dependencies"), self.pkg.get("dependencies"))
        self.assertEqual(raiz.get("devDependencies"), self.pkg.get("devDependencies"))
        self.assertEqual(self.lock["version"], self.pkg["version"], "versão do lockfile ≠ package.json")

    def test_every_locked_package_carries_an_integrity_hash(self):
        sem = [k for k, v in self.lock["packages"].items() if k and not v.get("link") and "integrity" not in v]
        self.assertEqual(sem, [], f"pacote sem integrity no lockfile: {sem[:5]}")

    @unittest.skipUnless((ROOT / "web" / "node_modules").is_dir(), "node_modules ausente")
    def test_every_installed_package_matches_the_locked_version(self):
        import json
        nm = ROOT / "web" / "node_modules"
        divergentes = []
        for pk in list(nm.glob("*/package.json")) + list(nm.glob("@*/*/package.json")):
            nome = str(pk.parent.relative_to(nm))
            instalada = json.loads(pk.read_text(encoding="utf-8")).get("version")
            travada = self.lock["packages"].get(f"node_modules/{nome}", {}).get("version")
            if travada and instalada != travada:
                divergentes.append((nome, instalada, travada))
        self.assertEqual(divergentes, [], f"instalado ≠ lockfile: {divergentes}")
