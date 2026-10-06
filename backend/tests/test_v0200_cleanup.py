"""v0.20.0 §54–55 — limpeza, e as travas que impedem a sujeira de voltar.

§54 manda procurar e remover código morto, imports mortos, arquivos antigos, versões duplicadas,
motores duplicados, documentação contraditória, mocks permanentes, TODO crítico, bandeiras obsoletas,
código experimental, seeds de teste, dado falso, scripts inúteis e endpoints órfãos. §55 manda NÃO
remover migrações.

Remover uma vez é fácil. O que este arquivo faz é diferente: transforma cada achado numa trava, para
que a próxima rodada não tenha de descobrir a mesma coisa de novo. Varredura é mais barata que
memória.

O QUE A VARREDURA DESTA RODADA ENCONTROU, e que estes testes agora impedem:

* `attach_pix()` e `attach_boleto()` gravavam instrução de pagamento que só um provedor brasileiro
  produz. Sem provedor, chamá-las exigiria valor inventado — código que, se ligado, MENTE.
* `retry_serializable()` contradizia a estratégia escolhida (devolver 409 e o cliente repete).
* `.docx` era ACEITO no envio, os leitores existiam, e nenhum estava ligado ao extrator: documento
  em Word subia sem texto nenhum, e o classificador recebia vazio em silêncio.
* A bandeira `public_directory_providers` era alterável pela administração e não ligava NADA.
* Os `invariants` de `config/plans.json` eram três strings que nenhum teste conferia.
"""
from __future__ import annotations

import ast
import json
import re
import unittest

from tests.support import ROOT, db_system, new_account

PKG = ROOT / "backend" / "impacto"
TESTES = ROOT / "backend" / "tests"


class NoDeadCodeReturnsTests(unittest.TestCase):
    """As funções removidas não voltam por engano, e o motivo fica legível no lugar delas."""

    def test_the_unreachable_payment_writers_stay_out(self):
        fonte = (PKG / "economics" / "payments.py").read_text(encoding="utf-8")
        for nome in ("def attach_pix", "def attach_boleto"):
            self.assertNotIn(nome, fonte,
                             "gravador de instrução de pagamento sem provedor: se ligado, mente")
        self.assertIn("se ligado, mente", fonte, "o motivo da remoção tem de ficar escrito")

    def test_the_payment_tables_were_kept_because_migrations_are_never_removed(self):
        """§55: migração não se remove. A tabela fica, esperando provedor."""
        with db_system() as c:
            for t in ("charge_pix", "charge_boleto"):
                self.assertTrue(
                    c.one("SELECT 1 FROM information_schema.tables WHERE table_name = $1", t),
                    f"{t} foi removida: migração não se remove")

    def test_the_retry_helper_does_not_come_back_contradicting_the_chosen_strategy(self):
        pool = (PKG / "db" / "pool.py").read_text(encoding="utf-8")
        self.assertNotIn("def retry_serializable", pool)
        http = (PKG / "http.py").read_text(encoding="utf-8")
        self.assertIn("concurrent_update", http,
                      "a estratégia é devolver 409 e o cliente repetir — tem de continuar lá")

    def test_no_module_level_function_in_the_package_is_unreachable(self):
        """Varredura: função de módulo que só aparece na própria definição é código morto.

        Handlers de rota, validadores de esquema e `main()` ficam de fora porque são chamados por
        decorador ou por framework — e não por nome.

        A contagem é feita em UMA passada de tokens sobre todo o repositório. A primeira versão
        deste teste rodava uma expressão regular por nome contra o texto concatenado inteiro — 1.700
        varreduras de alguns megabytes cada — e estourou dois minutos. Teste lento é teste que
        alguém desliga.
        """
        from collections import Counter

        definicoes: dict[str, str] = {}
        for f in PKG.rglob("*.py"):
            arvore = ast.parse(f.read_text(encoding="utf-8"))
            for no in arvore.body:              # só nível de módulo
                if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                decoradores = {
                    (d.func.id if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                     else d.id if isinstance(d, ast.Name) else "")
                    for d in no.decorator_list}
                if decoradores & {"route", "A", "field_validator", "model_validator"}:
                    continue
                if no.name in ("main", "__getattr__"):
                    continue
                definicoes[no.name] = f"{f.relative_to(PKG)}:{no.lineno}"

        ocorrencias: Counter[str] = Counter()
        identificador = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
        for raiz in (PKG, TESTES, ROOT / "scripts"):
            for f in raiz.rglob("*.py"):
                ocorrencias.update(identificador.findall(f.read_text(encoding="utf-8")))

        mortas = sorted(f"{onde} :: {nome}" for nome, onde in definicoes.items()
                        if ocorrencias[nome] <= 1)
        self.assertEqual(mortas, [],
                         "função de módulo nunca chamada (ligue ou remova):\n" + "\n".join(mortas))


class NoLeftoverMarkersTests(unittest.TestCase):
    def test_there_is_no_fixme_or_hack_marker_in_the_product(self):
        achados = []
        for raiz, padrao in ((PKG, "*.py"), (ROOT / "web" / "src", "*.ts*"),
                             (ROOT / "scripts", "*.py")):
            for f in raiz.rglob(padrao):
                for n, linha in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    if re.search(r"\b(FIXME|HACK|XXX:)\b", linha):
                        achados.append(f"{f.name}:{n}")
        self.assertEqual(achados, [], "marcador de pendência no produto: " + ", ".join(achados))

    def test_no_production_module_imports_a_test_helper(self):
        for f in PKG.rglob("*.py"):
            src = f.read_text(encoding="utf-8")
            self.assertNotIn("from tests", src, f"{f.name} importa apoio de teste")
            self.assertNotIn("import tests", src, f"{f.name} importa apoio de teste")

    def test_the_demo_seed_only_runs_outside_production(self):
        seed = (PKG / "seed_dev.py").read_text(encoding="utf-8")
        self.assertIn("development", seed)
        self.assertIn("EXEMPLO", seed.upper(),
                      "dado de demonstração tem de se identificar como fictício")


class FlagsAndInvariantsAreRealTests(unittest.TestCase):
    """Bandeira que não liga nada é pior que bandeira nenhuma: quem administra acredita ter escolhido."""

    @classmethod
    def setUpClass(cls):
        cls.plans = json.loads((ROOT / "config" / "plans.json").read_text(encoding="utf-8"))

    def test_every_declared_flag_is_read_by_some_code(self):
        corpo = "\n".join(f.read_text(encoding="utf-8") for f in PKG.rglob("*.py"))
        corpo += "\n".join(f.read_text(encoding="utf-8")
                           for f in (ROOT / "web" / "src").rglob("*.ts*"))
        mortas = [k for k in self.plans["flags"]
                  if k not in corpo
                  and k not in json.dumps(self.plans["plans"], ensure_ascii=False)]
        self.assertEqual(mortas, [],
                         "bandeira declarada que nenhum código lê: " + ", ".join(mortas))

    def test_the_directory_flag_actually_turns_the_directory_off(self):
        from tests.support import make_admin
        cli = new_account("osc")
        admin, _ = make_admin()
        # Pela ROTA de administração, não por INSERT: a tabela de bandeiras tem RLS que recusa até
        # o contexto de sistema, e é bom que recuse — foi ela que reprovou a primeira versão deste
        # teste. Testar pelo caminho real também prova que o interruptor da administração funciona.
        self.assertEqual(admin.put("/v1/admin/flags/public_directory_providers",
                                   {"enabled": False}).status, 200)
        try:
            r = cli.get("/v1/directory/professionals")
            self.assertEqual(r.status, 200, r)
            self.assertEqual(r.json["items"], [])
            self.assertTrue(r.json["disabled_by_platform"])
            self.assertIn("desligado pela administração", r.json["note"],
                          "o diretório vazio tem de dizer que foi desligado, não parecer vazio")
        finally:
            admin.put("/v1/admin/flags/public_directory_providers", {"enabled": True})
        self.assertNotIn("disabled_by_platform",
                         cli.get("/v1/directory/professionals").json,
                         "religado, o diretório volta a responder normalmente")

    def test_every_declared_invariant_points_at_a_test_that_exists(self):
        """Invariante no arquivo de configuração sem teste é promessa, não invariante."""
        inv = self.plans["invariants"]
        self.assertIsInstance(inv, dict, "os invariantes viraram objeto com o teste que os verifica")
        for chave, dado in inv.items():
            self.assertIn("claim", dado, chave)
            self.assertIn("verified_by", dado, chave)
            caminho = dado["verified_by"].split("::")[0]
            self.assertTrue((ROOT / caminho).exists(),
                            f"{chave}: o teste declarado não existe ({caminho})")
            if "::" in dado["verified_by"]:
                nome = dado["verified_by"].split("::")[1]
                self.assertIn(nome, (ROOT / caminho).read_text(encoding="utf-8"),
                              f"{chave}: {nome} não está em {caminho}")

    def test_a_config_key_nobody_reads_says_so(self):
        """`downgrade_grace_days` não é lida por ninguém — e agora declara isso em vez de fingir."""
        self.assertIn("_downgrade_grace_days_note", self.plans)
        self.assertIn("DECLARAÇÃO, não comportamento implementado",
                      self.plans["_downgrade_grace_days_note"])


class TextExtractionIsWiredTests(unittest.TestCase):
    """`.docx` era aceito e subia sem texto. O leitor existia e não estava ligado."""

    def test_the_accepted_office_formats_are_actually_extracted(self):
        from impacto.services import documents as D, formats as F
        docx = F.docx("Título", [("h1", "Cabeçalho"), ("p", "Parágrafo com acentuação e & < >.")])
        texto = D.extract_text(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", docx)
        self.assertIsNotNone(texto, ".docx é aceito no envio e não extraía texto nenhum")
        self.assertIn("acentuação", texto)

    def test_odt_is_extracted_too_since_formats_declares_it(self):
        from impacto.services import documents as D, formats as F
        odt = F.odt("Título", [("p", "Texto em ODT para conferência.")])
        texto = D.extract_text("application/vnd.oasis.opendocument.text", odt)
        self.assertIsNotNone(texto)
        self.assertIn("ODT", texto)

    def test_every_format_formats_py_claims_to_read_is_reachable(self):
        """O cabeçalho de `formats.py` declara quais formatos ele LÊ. A declaração tem de valer."""
        fonte = (PKG / "services" / "formats.py").read_text(encoding="utf-8")
        self.assertIn("docx e odt", fonte)
        extrator = (PKG / "services" / "documents.py").read_text(encoding="utf-8")
        for leitor in ("read_docx_text", "read_odt_text"):
            self.assertIn(leitor, extrator,
                          f"{leitor} existe e não é chamado pelo extrator")
