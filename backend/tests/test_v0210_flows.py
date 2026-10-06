"""Modelos de documento, processos mapeados e fluxos visuais — por perfil.

O QUE A AUDITORIA DESTA RODADA ENCONTROU

O pedido era "documentos modelos inseridos formatados e disponíveis, processos mapeados, fluxos
visuais identificados e visíveis em cada perfil". A auditoria achou três situações diferentes:

* modelos: 3 publicados e bem formatados — todos do lado de quem PROPÕE, e a tela de modelos não
  estava no menu de NENHUM perfil;
* processos: mapeados em `config/onboarding_paths.json` para 5 dos 6 perfis;
* fluxos visuais: o componente `Trail` existia, com CSS caprichado e três trilhas definidas, e era
  usado em UM lugar só — o detalhe de candidatura.

Estes testes travam as três correções. O mais importante deles é
`test_the_trail_is_used_in_more_than_one_place`: um componente de identidade usado uma vez só é um
componente que vai ser esquecido na próxima tela.
"""
from __future__ import annotations

import json
import re
import unittest

from tests.support import ROOT, db_system, new_account

WEB = ROOT / "web" / "src"


def q(sql, *a):
    with db_system() as c:
        return [dict(r) for r in c.query(sql, *a)]


class DocumentTemplatesTests(unittest.TestCase):

    def test_there_are_templates_for_both_sides_of_a_partnership(self):
        """Quem propõe e quem fomenta. Até a v0.20.0 só havia modelos do lado de quem propõe."""
        kinds = {r["code"]: r["kind"] for r in q("SELECT code, kind FROM document_templates"
                                                 " WHERE status = 'published'")}
        # Lado de quem propõe (v0.15.0)
        for code in ("projeto_tecnico_base", "plano_trabalho_mrosc", "plano_monitoramento_base"):
            self.assertIn(code, kinds)
        # Lado de quem fomenta (v0.21.0)
        self.assertEqual(kinds.get("edital_chamamento_mrosc"), "form")
        self.assertEqual(kinds.get("termo_parceria_mrosc"), "term")

    def test_every_published_template_is_formatted_not_raw_text(self):
        """Modelo sem seção, tipo de campo e obrigatoriedade é um arquivo de texto com nome bonito."""
        for t in q("SELECT id::text AS id, code FROM document_templates WHERE status = 'published'"):
            campos = q("SELECT section, position, key, label, field_type, required"
                       " FROM document_template_fields WHERE template_id = $1", t["id"])
            self.assertGreaterEqual(len(campos), 8, f"{t['code']} tem {len(campos)} campos")
            self.assertTrue(all(c["section"] for c in campos), f"{t['code']}: campo sem seção")
            self.assertTrue(all(c["label"] for c in campos), f"{t['code']}: campo sem rótulo")
            self.assertTrue(all(c["field_type"] for c in campos), f"{t['code']}: campo sem tipo")
            self.assertTrue(any(c["required"] for c in campos),
                            f"{t['code']}: nenhum campo obrigatório — completude não significaria nada")
            # Seções com posição própria: um modelo com tudo na mesma seção não é formatado.
            self.assertGreaterEqual(len({c["section"] for c in campos}), 3,
                                    f"{t['code']} tem menos de 3 seções")

    def test_the_new_templates_cite_the_law_they_come_from(self):
        """Estrutura sem fonte é estrutura inventada. Estes dois vêm de artigo citável."""
        for code, artigo in (("edital_chamamento_mrosc", "art. 24"),
                             ("termo_parceria_mrosc", "art. 42")):
            r = q("SELECT title, source_note FROM document_templates WHERE code = $1", code)[0]
            self.assertIn("13.019/2014", r["title"], f"{code} não nomeia a lei no título")
            self.assertIn(artigo, r["title"].lower().replace("art.", "art."),
                          f"{code} não nomeia o artigo")
            self.assertIn("13.019/2014", r["source_note"])
            # E manda conferir: a lei foi alterada, e um modelo que não avisa disso engana.
            self.assertIn("VIGENTE", r["source_note"].upper(),
                          f"{code} não manda conferir a redação vigente")

    def test_no_template_claims_to_be_an_official_form(self):
        """Todo modelo diz o que NÃO é — e manda conferir.

        A plataforma não distribui formulário oficial de terceiro. Um modelo que não declara isso
        seria usado como se fosse o documento do órgão, e a diferença só apareceria no protocolo.
        """
        NEGA = (r"não é", r"NÃO é", r"não substitui", r"não reproduz", r"não se assina",
                r"confira", r"CONFIRA")
        for r in q("SELECT code, source_note FROM document_templates WHERE status = 'published'"):
            nota = r["source_note"] or ""
            self.assertTrue(any(re.search(n, nota) for n in NEGA),
                            f"{r['code']} não diz o que NÃO é nem manda conferir: {nota!r}")

    def test_a_published_template_is_immutable(self):
        tid = q("SELECT id::text AS id FROM document_templates WHERE code = 'termo_parceria_mrosc'")[0]["id"]
        with self.assertRaises(Exception):
            with db_system() as c:
                c.run("UPDATE document_template_fields SET label = 'alterado' WHERE template_id = $1", tid)


class TemplatesAreReachableTests(unittest.TestCase):
    """Funcionalidade permitida e invisível é funcionalidade que não existe para quem usa."""

    def _nav(self) -> dict[str, list[str]]:
        s = (WEB / "app.tsx").read_text(encoding="utf-8")
        bloco = s[s.index("const NAV"):s.index("export function App()")]
        out = {}
        for m in re.finditer(r"  ([a-z]+): \[(.*?)\],?\n(?=  [a-z]+: \[|\};)", bloco, re.S):
            out[m.group(1)] = re.findall(r'\["([^"]+)",', m.group(2))
        return out

    def test_every_profile_with_documents_also_reaches_templates_and_assemblies(self):
        nav = self._nav()
        self.assertTrue(nav, "não consegui ler o NAV")
        falhas = []
        for perfil, itens in nav.items():
            if "/documentos" not in itens:
                continue      # individual e platform não têm cofre de documentos, por desenho
            for rota in ("/documentos/montagens", "/documentos/modelos"):
                if rota not in itens:
                    falhas.append(f"{perfil} tem /documentos mas não {rota}")
        self.assertEqual(falhas, [], "; ".join(falhas))

    def test_the_template_routes_do_not_restrict_profile(self):
        # As rotas sempre permitiram todos os perfis; o que faltava era o caminho clicável.
        s = (WEB / "app.tsx").read_text(encoding="utf-8")
        for rota in ('"/documentos/modelos"', '"/documentos/montagens"'):
            linha = next(ln for ln in s.splitlines() if rota in ln and "=>" in ln)
            self.assertNotRegex(linha, r"\]\s*,\s*\[",
                                f"{rota} ganhou restrição de perfil: {linha.strip()}")

    def test_the_templates_screen_lists_what_the_database_has(self):
        cli = new_account("government")
        r = cli.get("/v1/document-templates")
        self.assertEqual(r.status, 200, r.body)
        codes = {t["code"] for t in r.json["items"]}
        self.assertIn("edital_chamamento_mrosc", codes,
                      "o órgão público não enxerga o modelo de edital")
        self.assertIn("termo_parceria_mrosc", codes)


class VisualFlowsTests(unittest.TestCase):

    def _fontes(self):
        return list(WEB.rglob("*.tsx"))

    def test_the_trail_is_used_in_more_than_one_place(self):
        """O teste central deste arquivo.

        `Trail` é o elemento de identidade da plataforma — 9 etapas, CSS com linha conectora e anel
        pulsante na etapa atual, `aria-current="step"`. Até a v0.21.0 ele aparecia numa tela só, e
        três trilhas definidas em `trail.tsx` nunca chegavam a lugar nenhum. Um componente de
        identidade usado uma vez é um componente que a próxima tela vai esquecer.
        """
        usos = [f.relative_to(WEB).as_posix() for f in self._fontes()
                if f.name != "trail.tsx" and re.search(r"<(Trail|JourneyTrail)\b", f.read_text(encoding="utf-8"))]
        self.assertGreaterEqual(len(usos), 4,
                                f"a Trilha voltou a aparecer em poucos lugares: {usos}")

    def test_every_trail_defined_is_actually_rendered(self):
        """Trilha definida e nunca usada é a mesma coisa que não existir."""
        fonte = (WEB / "ui" / "trail.tsx").read_text(encoding="utf-8")
        definidas = set(re.findall(r"export const ([A-Z_]+_TRAIL)", fonte))
        self.assertTrue(definidas)
        texto = "\n".join(f.read_text(encoding="utf-8") for f in self._fontes() if f.name != "trail.tsx")
        orfas = sorted(d for d in definidas if d not in texto)
        self.assertEqual(orfas, [], f"trilhas definidas e nunca renderizadas: {orfas}")

    def test_the_project_lifecycle_has_a_map_and_not_only_a_dropdown(self):
        core = (WEB / "pages" / "core.tsx").read_text(encoding="utf-8")
        self.assertIn("PROJECT_PHASE_TRAIL", core,
                      "as 17 situações do projeto voltaram a não ter mapa em tela")

    def test_the_document_assembly_flow_left_the_ascii_diagram(self):
        core = (WEB / "pages" / "core.tsx").read_text(encoding="utf-8")
        self.assertIn("ASSEMBLY_TRAIL", core)
        # E as etapas da trilha são situações REAIS da tabela, não rótulos inventados para a tela.
        fonte = (WEB / "ui" / "trail.tsx").read_text(encoding="utf-8")
        trecho = fonte[fonte.index("ASSEMBLY_TRAIL"):fonte.index("] as const", fonte.index("ASSEMBLY_TRAIL"))]
        etapas = set(re.findall(r'\["([a-z_]+)",', trecho))
        # As situações REAIS saem do CHECK da tabela, não de uma lista copiada para o teste: copiar
        # criaria a segunda definição que divergiria na primeira situação nova.
        ddl = q("SELECT pg_get_constraintdef(oid) AS d FROM pg_constraint"
                " WHERE conrelid = 'document_assemblies'::regclass AND contype = 'c'"
                "   AND pg_get_constraintdef(oid) LIKE '%status%'")[0]["d"]
        reais = set(re.findall(r"'([a-z_]+)'::text", ddl))
        self.assertGreaterEqual(len(reais), 6, f"não consegui ler as situações do CHECK: {ddl}")
        self.assertTrue(etapas <= reais, f"etapas que não são situações reais: {etapas - reais}")

    def test_the_profile_journey_is_drawn_as_a_trail(self):
        ajuda = (WEB / "pages" / "help.tsx").read_text(encoding="utf-8")
        self.assertIn("JourneyTrail", ajuda)


class MappedProcessesTests(unittest.TestCase):

    def setUp(self):
        self.ob = json.loads((ROOT / "config" / "onboarding_paths.json").read_text(encoding="utf-8"))

    def test_every_organization_kind_that_signs_up_has_a_mapped_journey(self):
        caminhos = self.ob.get("paths") or self.ob
        tipos = {k for k in caminhos if k in ("osc", "company", "individual", "provider", "government")}
        self.assertEqual(tipos, {"osc", "company", "individual", "provider", "government"},
                         f"faltam jornadas para: {{'osc','company','individual','provider','government'}} - {tipos}")

    def test_every_step_is_detected_by_real_data_not_self_declaration(self):
        caminhos = self.ob.get("paths") or self.ob
        sem_detector = []
        for tipo, cfg in caminhos.items():
            if not isinstance(cfg, dict) or "steps" not in cfg:
                continue
            for s in cfg["steps"]:
                if not s.get("detector"):
                    sem_detector.append(f"{tipo}.{s.get('key')}")
        self.assertEqual(sem_detector, [],
                         "etapa marcada por autodeclaração em vez de dado real: "
                         + ", ".join(sem_detector))

    def test_the_journey_is_served_per_profile(self):
        for kind in ("osc", "company", "government", "provider"):
            cli = new_account(kind)
            r = cli.get("/v1/help/start")
            self.assertEqual(r.status, 200, f"{kind}: {r.body}")
            self.assertTrue(r.json["steps"], f"{kind} recebeu jornada vazia")
            for s in r.json["steps"]:
                for campo in ("key", "title", "done"):
                    self.assertIn(campo, s, f"{kind}: etapa sem {campo}")

    def test_the_journey_declares_that_it_is_a_hypothesis(self):
        # O arquivo se declara HIPÓTESE. Isso é honesto e precisa continuar visível na tela, em vez
        # de a jornada passar por validada só porque ficou bonita.
        bruto = (ROOT / "config" / "onboarding_paths.json").read_text(encoding="utf-8")
        self.assertIn("HIP", bruto.upper(), "a jornada deixou de se declarar hipótese")
        ajuda = (WEB / "pages" / "help.tsx").read_text(encoding="utf-8")
        self.assertIn("validação editorial", ajuda,
                      "a tela parou de dizer que a jornada está em validação")
