"""Portão da identidade oficial: o que a interface mostra TEM de derivar de `web/brand/`.

Cada teste aqui existe por um motivo concreto encontrado ao integrar o pacote recebido:

- a cópia solta que veio no ZIP (`web/public/impacto-brand/`) não tinha fonte nem gerador — por isso
  o `tokens.css` versionado tem de ser exatamente o que o gerador produz do `tokens.json`;
- o `app.config.ts` recebido apontava o logo para um CDN de terceiro — por isso nenhuma referência a
  host externo passa;
- o CSS antigo tinha texto branco sobre amarelo em dois lugares e desenhava a marca em CSS — por isso
  o aliasing é conferido token a token e a marca tem de ser a imagem oficial;
- um item de menu sem ícone deixa um buraco na barra — por isso toda rota de menu tem ícone mapeado.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
BRAND = WEB / "brand"
STYLES = (WEB / "src" / "styles.css").read_text(encoding="utf-8")
TOKENS_CSS = (BRAND / "tokens.css").read_text(encoding="utf-8")


def _sem_comentarios(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


class TheTokensAreGeneratedFromTheSingleSourceTests(unittest.TestCase):
    def test_tokens_css_is_exactly_what_the_generator_produces(self):
        sys.path.insert(0, str(BRAND))
        try:
            import generate_tokens  # noqa: PLC0415 — módulo da pasta da identidade
        finally:
            sys.path.pop(0)
        tokens = json.loads((BRAND / "tokens.json").read_text(encoding="utf-8"))
        self.assertEqual(generate_tokens.gerar(tokens), TOKENS_CSS,
                         "tokens.css divergiu do tokens.json. Regere: python3 web/brand/generate_tokens.py")

    def test_the_generator_runs_as_a_script_and_changes_nothing(self):
        antes = TOKENS_CSS
        r = subprocess.run([sys.executable, str(BRAND / "generate_tokens.py")], capture_output=True, text=True,
                           cwd=ROOT, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((BRAND / "tokens.css").read_text(encoding="utf-8"), antes)

    def test_the_three_themes_define_the_same_semantic_tokens(self):
        """Token definido só num tema é a origem clássica de texto ilegível no outro."""
        def nomes(bloco: str) -> set[str]:
            return set(re.findall(r"--pi-color-([a-z0-9-]+):", bloco))
        claro = nomes(TOKENS_CSS.split('[data-theme="light"]')[0])
        escuro = nomes(TOKENS_CSS.split('[data-theme="dark"] {')[1].split("}")[0])
        alto = nomes(TOKENS_CSS.split('[data-theme="high-contrast"] {')[1].split("}")[0])
        self.assertTrue(escuro <= claro, f"tokens só no escuro: {sorted(escuro - claro)}")
        self.assertTrue(alto <= claro, f"tokens só no alto contraste: {sorted(alto - claro)}")
        self.assertEqual(escuro, alto, "escuro e alto contraste não cobrem o mesmo conjunto")
        self.assertIn("color-scheme: light;\n}", TOKENS_CSS.split('[data-theme="high-contrast"] {')[1][:4000],
                      "alto contraste é de canvas claro e tem de declarar color-scheme: light")


class TheAppStylesheetWearsTheOfficialTokensTests(unittest.TestCase):
    def test_every_alias_points_to_a_token_that_exists(self):
        definidos = set(re.findall(r"(--pi-[a-z0-9-]+):", TOKENS_CSS))
        usados = set(re.findall(r"var\((--pi-[a-z0-9-]+)", STYLES))
        self.assertTrue(usados, "styles.css não usa nenhum token oficial")
        self.assertEqual(usados - definidos, set(), "styles.css usa token que tokens.css não define")

    def test_no_literal_color_survives_outside_comments(self):
        corpo = _sem_comentarios(STYLES)
        literais = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d", corpo)
        self.assertEqual(literais, [], f"cor literal fora dos tokens: {literais[:8]}")

    def test_white_never_sits_on_yellow(self):
        """Regra da marca. Conferida regra a regra: fundo amarelo + cor branca na mesma declaração."""
        for regra in re.findall(r"\{[^}]*\}", _sem_comentarios(STYLES)):
            # Só quando o FUNDO é o amarelo: `box-shadow: inset … var(--ipe)` (a barrinha do item ativo
            # na navegação navy) não é fundo amarelo, e a primeira versão deste teste acusava isso.
            if re.search(r"background(?:-color)?:\s*var\(--ipe\)", regra):
                self.assertNotRegex(regra, r"color:\s*(#fff|white|var\(--sobre-tinta\))",
                                    f"texto branco sobre amarelo: {regra[:120]}")

    def test_the_official_stylesheets_are_imported_first(self):
        self.assertRegex(STYLES, r'@import "\.\./brand/tokens\.css";\s*\n@import "\.\./brand/components\.css";')
        self.assertLess(STYLES.index('@import "../brand/tokens.css"'), STYLES.index(":root {"))

    def test_the_mark_is_the_official_image_not_css(self):
        self.assertNotIn("brand-mark", STYLES)
        for arq in ("src/app.tsx", "src/pages/public.tsx", "src/pages/help.tsx"):
            self.assertNotIn("brand-mark", (WEB / arq).read_text(encoding="utf-8"), arq)
        brand = (WEB / "src" / "ui" / "brand.tsx").read_text(encoding="utf-8")
        for src in re.findall(r'"(/brand/[^"]+\.png)"', brand):
            self.assertTrue((WEB / "public" / src.lstrip("/")).exists(), f"logo referenciado não existe: {src}")
        self.assertIn("157", brand, "o limite do raster (157×151) tem de estar escrito onde o tamanho é escolhido")

    def test_the_rail_children_do_not_shrink(self):
        """O logo oficial foi cortado a 24px na primeira renderização: flex em coluna com altura fixa
        espreme os filhos. A regra que impede isso tem de continuar lá."""
        self.assertIn(".rail > * { flex-shrink: 0; }", STYLES)


class NothingPointsOutsideTheProductTests(unittest.TestCase):
    HOSTS_PROIBIDOS = ("manuscdn", "manus.space", "files.manus", "cdn.", "unpkg.com", "jsdelivr", "googleapis")

    def test_no_front_file_references_a_third_party_host(self):
        fontes = list((WEB / "src").rglob("*.ts*")) + [WEB / "index.html", WEB / "public" / "manifest.webmanifest",
                                                         WEB / "public" / "offline.html"]
        for f in fontes:
            texto = f.read_text(encoding="utf-8")
            for host in self.HOSTS_PROIBIDOS:
                self.assertNotIn(host, texto, f"{f.relative_to(ROOT)} aponta para {host}")

    def test_the_rejected_files_from_the_package_did_not_come_in(self):
        for caminho in ("app.config.ts", "server.mjs", "manus-webdev.json", "scripts/share_demo.py",
                        "web/public/manus-routes.json", "web/public/impacto-brand", "RELEASE_AUDIT_LIVE.md"):
            self.assertFalse((ROOT / caminho).exists(), f"{caminho} entrou apesar da triagem")


class TheServedAssetsExistAndMatchTheManifestTests(unittest.TestCase):
    def test_manifest_icons_and_colors(self):
        d = json.loads((WEB / "public" / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(d["theme_color"], "#16233B")
        self.assertEqual(d["background_color"], "#F6F8F9")
        self.assertEqual({i["sizes"] for i in d["icons"]}, {"192x192", "512x512"})
        self.assertIn("maskable", {i.get("purpose") for i in d["icons"]})
        for i in d["icons"]:
            self.assertTrue((WEB / "public" / i["src"].lstrip("/")).exists(), i["src"])

    def test_index_html_links_the_official_favicons(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('content="#16233B"', html)
        for href in re.findall(r'rel="(?:icon|apple-touch-icon)"[^>]*href="([^"]+)"', html):
            self.assertTrue((WEB / "public" / href.lstrip("/")).exists(), href)
        self.assertNotIn("favicon.svg", html)

    def test_the_built_bundle_carries_the_identity(self):
        dist = WEB / "dist"
        css = list((dist / "assets").glob("styles-*.css")) if dist.exists() else []
        if not css:
            self.skipTest("web/dist não compilado")
        texto = css[0].read_text(encoding="utf-8")
        self.assertIn("--pi-color-brand-primary: #FFD43B", texto)
        self.assertIn("--pi-color-brand-primary: #FFD95A", texto, "tema escuro ausente do bundle")
        self.assertNotIn("Lora", texto, "a identidade não tem serifa; Lora tinha de sair")
        self.assertNotIn("@import", texto, "o esbuild tinha de embutir os @import")


class EveryMenuRouteHasAnOfficialIconTests(unittest.TestCase):
    def test_icon_map_only_names_icons_that_exist(self):
        icon = (WEB / "src" / "ui" / "icon.tsx").read_text(encoding="utf-8")
        catalogo = {i["name"] for i in json.loads((BRAND / "icon-catalog.json").read_text(encoding="utf-8"))["icons"]}
        importados = set(re.findall(r'"\.\./\.\./brand/icons/([^"]+)\.svg"', icon))
        for rel in importados:
            self.assertTrue((BRAND / "icons" / f"{rel}.svg").exists(), rel)
        nomes = set(re.findall(r'"([a-z]+/[a-z-]+)": [a-zA-Z]+,', icon))
        self.assertTrue(nomes <= catalogo, f"ícone fora do catálogo: {sorted(nomes - catalogo)}")

    def test_every_route_in_the_static_menus_has_an_icon(self):
        app = (WEB / "src" / "app.tsx").read_text(encoding="utf-8")
        nav = app[app.index("const NAV"):app.index("const KIND_LABEL")]
        rotas = set(re.findall(r'\["(/[^"]*)", "', nav))
        icon = (WEB / "src" / "ui" / "icon.tsx").read_text(encoding="utf-8")
        mapa = icon[icon.index("ICONE_DA_ROTA"):]
        mapeadas = set(re.findall(r'"(/[^"]*)": "', mapa))
        self.assertEqual(sorted(rotas - mapeadas), [], "rota de menu sem ícone oficial")


class TheLimitsOfTheIdentityAreWrittenDownTests(unittest.TestCase):
    def test_readme_states_license_raster_and_fonts(self):
        readme = (BRAND / "README.md").read_text(encoding="utf-8")
        for frase in ("Licença da marca não comprovada", "Logo master é raster", "Fontes não embarcadas"):
            self.assertIn(frase, readme, frase)
        self.assertTrue((BRAND / "ASSET_LICENSE_REGISTER.md").exists())
