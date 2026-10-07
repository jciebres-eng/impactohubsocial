"""Cadeia de suprimentos do frontend: o que vai para o pacote é reprodutível.

A auditoria desta versão apontou que `web/` não tem `package-lock.json`. Sem lockfile, dois
`npm install` em datas diferentes podem resolver versões transitivas diferentes, e
`npm audit --omit=dev` audita a árvore que acabou de ser resolvida — não necessariamente a que foi
para produção.

Gerar o lockfile exige rede até o registro npm, que este ambiente não tem (403 em todo pacote).
Escrever um lockfile à mão, com hashes de integridade que ninguém verificou, seria inventar
justamente o artefato cuja única função é ser verificável. Então a dívida está declarada em
`TECHNICAL_DEBT_REGISTER.md` (D-SUP1) e o que SOBRA sob controle fica travado aqui:

* toda dependência que entra no pacote construído tem versão exata;
* uma faixa `^` só é tolerada se estiver na lista de exceções abaixo, com motivo escrito;
* a lista de exceções tem teto — ela não pode crescer em silêncio;
* o CI gera o lockfile quando ele não existe, e usa `npm ci` quando existe.
"""
from __future__ import annotations

import json
import unittest

from tests.support import ROOT

PACOTE = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
TODAS = {**PACOTE.get("dependencies", {}), **PACOTE.get("devDependencies", {})}

# Dependências que o `build.mjs` usa para PRODUZIR o pacote servido. Estas não admitem faixa.
NO_PACOTE = {"react", "react-dom", "esbuild", "typescript"}

# Exceção com motivo, no mesmo formato de `SEM_ROTA`: a faixa é tolerada porque a versão exata não
# pode ser determinada aqui — o pacote não está instalado e o registro npm está inacessível.
FAIXA_TOLERADA = {
    "@types/react": "tipagem de tempo de compilação; não vai para o pacote; não instalado neste ambiente, "
                    "logo a versão exata não pode ser lida do node_modules sem inventar número",
    "@types/react-dom": "tipagem de tempo de compilação; não vai para o pacote; não instalado neste ambiente, "
                        "logo a versão exata não pode ser lida do node_modules sem inventar número",
    "@capacitor/cli": "empacotamento mobile (F1: nunca construído); não vai para o pacote web; não instalado",
    "@capacitor/core": "empacotamento mobile (F1: nunca construído); não vai para o pacote web; não instalado",
    "@capacitor/android": "empacotamento mobile (F1: nunca construído); não vai para o pacote web; não instalado",
    "@capacitor/ios": "empacotamento mobile (F1: nunca construído); não vai para o pacote web; não instalado",
    "@capacitor/preferences": "empacotamento mobile (F1: nunca construído); não vai para o pacote web; não instalado",
}


class WhatGoesIntoTheBundleIsPinnedTests(unittest.TestCase):

    def test_every_dependency_in_the_bundle_has_an_exact_version(self):
        faixas = {n: v for n, v in TODAS.items()
                  if n in NO_PACOTE and not v[0].isdigit()}
        self.assertEqual({}, faixas,
                         f"dependência do pacote construído com faixa de versão: {faixas} — "
                         "sem lockfile, uma faixa significa que o bundle publicado pode diferir do testado")

    def test_the_four_bundle_dependencies_are_all_still_declared(self):
        """Se `react` sair daqui, o teste acima fica verde sem proteger nada."""
        self.assertEqual(NO_PACOTE, NO_PACOTE & set(TODAS),
                         f"dependência do pacote desapareceu de package.json: {NO_PACOTE - set(TODAS)}")

    def test_every_version_range_is_declared_with_a_reason(self):
        sem_motivo = [n for n, v in TODAS.items()
                      if not v[0].isdigit() and n not in FAIXA_TOLERADA]
        self.assertEqual([], sem_motivo,
                         f"faixa de versão sem motivo escrito: {sem_motivo} — "
                         "ou fixe a versão, ou declare por que ela não pode ser fixada")

    def test_the_exemption_list_has_no_stale_entries(self):
        """Dependência removida do projeto não deve continuar listada como exceção."""
        fantasmas = [n for n in FAIXA_TOLERADA if n not in TODAS]
        self.assertEqual([], fantasmas, f"exceção para dependência que não existe mais: {fantasmas}")

    def test_the_exemption_list_cannot_grow_quietly(self):
        """Teto explícito: a próxima faixa tolerada exige mexer neste número e explicar."""
        self.assertLessEqual(len(FAIXA_TOLERADA), 7,
                             "a lista de exceções cresceu — cada entrada nova precisa de decisão consciente")

    def test_every_reason_is_actually_a_reason(self):
        for nome, motivo in FAIXA_TOLERADA.items():
            with self.subTest(dependencia=nome):
                self.assertGreaterEqual(len(motivo), 40, "motivo curto demais para ser um motivo")

    def test_no_exempted_dependency_is_one_that_goes_into_the_bundle(self):
        """A exceção não pode ser usada para afrouxar o que o teste principal protege."""
        conflito = NO_PACOTE & set(FAIXA_TOLERADA)
        self.assertEqual(set(), conflito, f"dependência do pacote na lista de exceções: {conflito}")


class TheMissingLockfileIsDeclaredNotHiddenTests(unittest.TestCase):
    """A dívida tem de estar escrita. Lacuna de segurança não declarada é lacuna dobrada."""

    def test_the_debt_register_names_the_missing_lockfile(self):
        texto = (ROOT / "TECHNICAL_DEBT_REGISTER.md").read_text(encoding="utf-8")
        self.assertIn("package-lock.json", texto)
        self.assertIn("D-SUP1", texto)
        self.assertIn("registry.npmjs.org", texto,
                      "o registro de dívida precisa mostrar o erro real, não apenas afirmar que houve um")

    def test_the_debt_entry_says_what_to_run_to_close_it(self):
        texto = (ROOT / "TECHNICAL_DEBT_REGISTER.md").read_text(encoding="utf-8")
        self.assertIn("npm install --package-lock-only", texto,
                      "dívida sem o comando que a fecha vira dívida permanente")

    def test_the_lockfile_claim_matches_reality(self):
        """Se alguém commitar o lockfile, este teste avisa que a dívida pode ser removida.

        O par oposto do teste acima: o registro não deve continuar afirmando que falta um arquivo
        que já existe. Documentação que descreve um estado antigo é pior que documentação ausente.
        """
        existe = (ROOT / "web" / "package-lock.json").exists()
        texto = (ROOT / "TECHNICAL_DEBT_REGISTER.md").read_text(encoding="utf-8")
        if existe:
            self.fail("web/package-lock.json agora existe: remova D-SUP1 do registro de dívida, "
                      "troque `npm install` por `npm ci` no CI e apague este ramo do teste")
        self.assertIn("não existe", texto)


if __name__ == "__main__":
    unittest.main()
