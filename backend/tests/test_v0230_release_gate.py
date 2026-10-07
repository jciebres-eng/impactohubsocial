"""Portão de release: versão única, manifesto reconciliado, ambiente declarado.

POR QUE ESTE ARQUIVO EXISTE

Uma auditoria externa da v0.23.0 encontrou algo que a suíte não pegava: `VERSION` dizia `0.23.0`
enquanto `backend/pyproject.toml` e `web/package.json` diziam `0.14.0` — nove versões atrás. Nada
reprovava, porque nada conferia: o runtime lê o arquivo `VERSION`, então o produto funcionava e os
dois metadados ficaram parados desde a v0.14.0.

Isso importa fora do runtime. Quem empacota, quem audita e quem publica leem os metadados — e três
fontes de versão com duas erradas é a forma mais barata de um release sair com o número errado.

A correção foi atualizar os dois arquivos. A TRAVA é este teste.
"""
from __future__ import annotations

import json
import re
import subprocess
import unittest

from tests.support import ROOT


def _versao_declarada() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


class ThereIsOneVersionAndEverybodyAgreesWithItTests(unittest.TestCase):
    """`VERSION` é a fonte. Quem repete o número tem de repetir o mesmo."""

    def test_the_version_file_is_the_source_the_runtime_reads(self):
        from impacto.config import VERSION
        self.assertEqual(_versao_declarada(), VERSION,
                         "o runtime leria uma versão diferente da declarada no arquivo")

    def test_the_backend_package_metadata_matches(self):
        texto = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', texto, re.M)
        self.assertIsNotNone(m, "pyproject.toml sem declaração de versão")
        self.assertEqual(_versao_declarada(), m.group(1),
                         "pyproject.toml declara versão diferente de VERSION — foi exatamente o "
                         "defeito que a auditoria externa da v0.23.0 encontrou (0.14.0 vs 0.23.0)")

    def test_the_frontend_package_metadata_matches(self):
        d = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(_versao_declarada(), d["version"],
                         "package.json declara versão diferente de VERSION")

    def test_the_openapi_document_carries_the_same_version(self):
        d = json.loads((ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
        self.assertEqual(_versao_declarada(), d["info"]["version"],
                         "o OpenAPI publicado declara outra versão: quem integra leria o número errado")

    def test_the_readme_title_carries_the_current_version(self):
        """O título do README é o primeiro lugar onde alguém lê a versão."""
        primeira = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()[0]
        self.assertIn(_versao_declarada(), primeira,
                      f"o título do README não traz a versão corrente: {primeira!r}")

    def test_the_changelog_has_an_entry_for_this_version(self):
        texto = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## [{_versao_declarada()}]", texto,
                      "versão sem entrada no changelog: release sem registro do que mudou")

    def test_the_previous_version_was_snapshotted(self):
        """A regra de versionamento desta base: nunca sobrescrever documento sem snapshot."""
        atual = _versao_declarada()
        anteriores = sorted(p.name for p in (ROOT / "history").iterdir() if p.is_dir())
        self.assertTrue(anteriores, "nenhum snapshot em history/")
        self.assertNotIn(f"v{atual}", anteriores,
                         "existe snapshot da versão CORRENTE: o snapshot é da anterior")
        # A versão imediatamente anterior tem de estar lá.
        maior, menor, _ = atual.split(".")
        anterior = f"v{maior}.{int(menor) - 1}.0"
        self.assertIn(anterior, anteriores,
                      f"falta o snapshot de {anterior} em history/: {anteriores[-4:]}")

    def test_no_version_number_is_hard_coded_in_the_application_code(self):
        """Número de versão em literal no código é a quarta fonte de verdade."""
        suspeitos = []
        for f in (ROOT / "backend" / "impacto").rglob("*.py"):
            texto = f.read_text(encoding="utf-8")
            for linha, conteudo in enumerate(texto.splitlines(), 1):
                if re.search(r'"0\.\d+\.\d+"', conteudo) and "VERSION" not in conteudo:
                    # Versão de MOTOR (`engine_version`) e de prompt são outra coisa: identificam o
                    # algoritmo que produziu um resultado, e não a versão do pacote.
                    if any(t in conteudo for t in ("engine_version", "engine", "@1.0", "prompt",
                                                   "local-", "chain_version")):
                        continue
                    suspeitos.append(f"{f.relative_to(ROOT)}:{linha}")
        self.assertEqual([], suspeitos,
                         f"versão de pacote em literal no código: {suspeitos}")


class TheManifestAndTheRepositoryAgreeTests(unittest.TestCase):
    """`arquivos rastreados ⊆ arquivos físicos`, e toda exceção é explicada."""

    @classmethod
    def setUpClass(cls):
        manifesto = ROOT / f"IMPACTO_v{_versao_declarada()}_TRACEABILITY.json"
        cls.existe = manifesto.exists()
        if cls.existe:
            cls.man = {a["file"] for a in json.loads(manifesto.read_text(encoding="utf-8"))["files"]}
        cls.git = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                     text=True).stdout.split())

    #: Arquivos versionados que NÃO entram no manifesto, com o motivo. As três primeiras entradas
    #: são auto-referência: um manifesto não pode conter o próprio hash. As demais são registro
    #: histórico de execução, excluído por `scripts/make_release.py` — o pacote distribui o
    #: software, não o log das versões anteriores.
    FORA_DO_MANIFESTO = {
        "IMPACTO_v0.23.0_TRACEABILITY.json": "auto-referência: o manifesto não contém o próprio hash",
        "RELEASE_MANIFEST.csv": "auto-referência: gerado no empacotamento, depois do manifesto",
        "RELEASE_MANIFEST.sha256": "auto-referência: é a lista de hashes do pacote",
    }

    #: Prefixos de caminho excluídos do pacote por regra explícita em `scripts/make_release.py`.
    PREFIXOS_EXCLUIDOS = ("docs/evidence/", "history/")

    def test_the_manifest_exists_for_this_version(self):
        self.assertTrue(self.existe, "não há manifesto de rastreabilidade para a versão corrente")

    def test_every_manifest_entry_is_a_real_tracked_file(self):
        """Manifesto apontando para arquivo que não existe é rastreabilidade de ficção."""
        if not self.existe:
            self.skipTest("sem manifesto")
        fantasmas = sorted(self.man - self.git)
        self.assertEqual([], fantasmas,
                         f"manifesto cita arquivo que não está no repositório: {fantasmas[:10]}")

    def test_every_tracked_file_is_either_in_the_manifest_or_excluded_with_a_reason(self):
        if not self.existe:
            self.skipTest("sem manifesto")
        inexplicados = []
        for caminho in sorted(self.git - self.man):
            if caminho in self.FORA_DO_MANIFESTO:
                continue
            if any(caminho.startswith(p) for p in self.PREFIXOS_EXCLUIDOS):
                continue
            inexplicados.append(caminho)
        self.assertEqual([], inexplicados,
                         "arquivo versionado fora do manifesto e sem motivo declarado: "
                         f"{inexplicados}")

    def test_the_declared_total_matches_the_list(self):
        if not self.existe:
            self.skipTest("sem manifesto")
        manifesto = ROOT / f"IMPACTO_v{_versao_declarada()}_TRACEABILITY.json"
        d = json.loads(manifesto.read_text(encoding="utf-8"))
        self.assertEqual(d["files_total"], len(d["files"]),
                         "o total declarado não bate com a lista: o número que alguém cita estaria errado")

    def test_every_exclusion_reason_is_written(self):
        for arquivo, motivo in self.FORA_DO_MANIFESTO.items():
            with self.subTest(arquivo=arquivo):
                self.assertGreaterEqual(len(motivo), 40,
                                        "exclusão sem motivo escrito é exclusão de conveniência")


if __name__ == "__main__":
    unittest.main()
