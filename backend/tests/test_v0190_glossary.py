"""v0.19.0 — o vocabulário oficial não pode divergir do código (FASE A).

ERRO QUE ESTES TESTES IMPEDEM. A API devolve `flagged`, a tela escreve "marcada" e o texto de ajuda diz
"sinalizada". Três palavras, um conceito — e quem desenha escolhe uma por conta. Pior: alguém acrescenta
um valor de enum numa migração e a interface passa a mostrar a chave crua em inglês, porque ninguém
lembrou de criar o rótulo.

ESTRATÉGIA. `config/glossary.json` é a origem do rótulo. `impacto/core/glossary.py` declara DE ONDE saem
os valores que existem de verdade (atributo Python, coluna de migração, varredura de código). Os testes
comparam as duas coisas nas duas direções: valor sem rótulo reprova, rótulo órfão reprova.

E, para que a guarda não seja decorativa, `test_o_detector_realmente_reprova` adultera o documento em
memória e exige que o detector acuse. Guarda que nunca falha não é guarda.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest

from impacto.core import glossary as G
from tests.support import ROOT, db_system, new_account


class GlossaryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = G.load()

    # ------------------------------------------------------------------ cobertura contra o código vivo
    def test_todo_valor_vivo_tem_rotulo_e_todo_rotulo_tem_valor_vivo(self):
        divergencias = G.missing(self.doc)
        self.assertEqual(divergencias, {}, "glossário fora de sincronia com o código:\n"
                         + json.dumps(divergencias, ensure_ascii=False, indent=2))

    def test_todo_dominio_do_glossario_declara_de_onde_vem(self):
        documentados, declarados = set(self.doc["domains"]), set(G.SURFACES)
        self.assertEqual(documentados - declarados, set(),
                         "domínio no glossário sem origem declarada em SURFACES — não dá para conferir")
        self.assertEqual(declarados - documentados, set(),
                         "origem declarada em SURFACES sem domínio no glossário")

    def test_o_detector_realmente_reprova(self):
        """Prova de que a guarda não é decorativa: documento adulterado tem de acusar."""
        forjado = json.loads(json.dumps(self.doc))
        forjado["domains"]["claim_status"]["terms"].pop("flagged")
        forjado["domains"]["match_signal"]["terms"]["sinal_que_nao_existe"] = {
            "label": {"pt-BR": "x", "en": "x", "es": "x"}, "definition": "x"}
        acusou = G.missing(forjado)
        self.assertEqual(acusou.get("claim_status", {}).get("undocumented"), ["flagged"])
        self.assertEqual(acusou.get("match_signal", {}).get("stale"), ["sinal_que_nao_existe"])

    # ------------------------------------------------------------------ qualidade de cada termo
    def test_todo_termo_tem_os_tres_idiomas_e_uma_definicao(self):
        faltas = []
        for nome, dominio in self.doc["domains"].items():
            for chave, termo in dominio["terms"].items():
                for loc in self.doc["locales"]:
                    valor = termo["label"].get(loc)
                    if not valor or not valor.strip():
                        faltas.append(f"{nome}.{chave}: rótulo {loc} vazio")
                    elif len(valor) > 2000:
                        faltas.append(f"{nome}.{chave}: rótulo {loc} acima do limite da tabela translations")
                definicao = termo.get("definition") or ""
                if len(definicao.strip()) < 20:
                    faltas.append(f"{nome}.{chave}: definição curta demais para servir a quem desenha")
        self.assertEqual(faltas, [], "\n".join(faltas))

    def test_todo_dominio_diz_onde_o_termo_aparece_na_api(self):
        for nome, dominio in self.doc["domains"].items():
            self.assertTrue((dominio.get("appears_in") or "").strip(),
                            f"{nome} não diz onde aparece — quem desenha não consegue achar o estado")
            self.assertTrue((dominio.get("title") or "").strip(), f"{nome} sem título")

    def test_chave_e_namespace_cabem_na_tabela_translations(self):
        import re
        ns_ok, key_ok = re.compile(r"^[a-z0-9_]{2,40}$"), re.compile(r"^[a-z0-9_.]{2,80}$")
        for nome, dominio in self.doc["domains"].items():
            self.assertRegex(f"g_{nome}", ns_ok)
            for chave in dominio["terms"]:
                self.assertRegex(chave, key_ok, f"{nome}.{chave} não cabe em translations.key")

    # ------------------------------------------------------------------ acordo com os rótulos da API
    def test_os_rotulos_da_api_sao_os_mesmos_do_glossario(self):
        """Os dicionários de rótulo que a API já devolve têm de dizer a MESMA palavra do glossário.

        É aqui que o produto deixa de ter duas verdades: se alguém reescrever STATUS_LABEL sem passar
        pelo glossário, este teste acusa a divergência pelo texto, não só pela chave.
        """
        from impacto.core import evidence
        from impacto.impact import claims, frameworks, lookups, seals
        from impacto.impact import equity
        pares = [
            ("claim_status", claims.STATUS_LABEL),
            ("seal_status", seals.STATUS_LABEL),
            ("seal_revocation_reason", seals.REVOCATION_LABEL),
            ("suggestion_origin", lookups.ORIGIN_LABEL),
            ("framework_relation", frameworks.RELATION_LABEL),
            ("framework_lens", frameworks.LENS_LABEL),
            ("equity_standing", equity.STANDING_LABEL),
            ("confidence_band", evidence.BAND_LABEL),
        ]
        pt = G.labels("pt-BR", self.doc)
        divergentes = []
        for dominio, mapa in pares:
            for chave, rotulo in mapa.items():
                chave = chave.value if hasattr(chave, "value") else str(chave)
                oficial = pt[dominio].get(chave)
                if oficial is None:
                    # apelido documentado (ex.: insufficient_data == insufficient)
                    for k, termo in self.doc["domains"][dominio]["terms"].items():
                        if chave in (termo.get("aliases") or ()):
                            oficial = termo["label"]["pt-BR"]
                            break
                if oficial != rotulo:
                    divergentes.append(f"{dominio}.{chave}: API={rotulo!r} glossário={oficial!r}")
        self.assertEqual(divergentes, [], "\n".join(divergentes))

    def test_metodo_de_normalizacao_mantem_o_rotulo_de_equity(self):
        from impacto.impact import equity
        pt = G.labels("pt-BR", self.doc)["equity_method"]
        for chave, spec in equity.METHODS.items():
            self.assertEqual(spec["label"], pt[chave], f"rótulo de {chave} divergiu do glossário")

    # ------------------------------------------------------------------ sincronia com i18n e markdown
    def test_i18n_e_markdown_estao_em_sincronia(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_glossary.py"), "--check"],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_i18n_tem_os_namespaces_do_glossario_nos_tres_idiomas(self):
        i18n = json.loads((ROOT / "config" / "i18n.json").read_text(encoding="utf-8"))
        for loc in self.doc["locales"]:
            espacos = i18n["locales"][loc]
            for nome, dominio in self.doc["domains"].items():
                ns = f"g_{nome}"
                self.assertIn(ns, espacos, f"{ns} ausente em {loc}")
                self.assertEqual(set(espacos[ns]), set(dominio["terms"]), f"{ns} em {loc} com chaves diferentes")


class GlossaryInDatabaseTests(unittest.TestCase):
    """O glossário só vale se chegar ao banco e à API. Aqui roda contra PostgreSQL de verdade."""

    @classmethod
    def setUpClass(cls):
        cls.doc = G.load()

    def test_a_migracao_sincronizou_os_rotulos_para_translations(self):
        esperado = sum(len(d["terms"]) for d in self.doc["domains"].values()) * len(self.doc["locales"])
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM translations WHERE namespace LIKE 'g\\_%'")
        self.assertEqual(n, esperado, "translations não recebeu o glossário — rode as migrações")

    def test_cada_termo_do_glossario_existe_no_banco_no_idioma_certo(self):
        faltas = []
        with db_system() as c:
            rows = c.query("SELECT locale, namespace, key, value FROM translations"
                           " WHERE namespace LIKE 'g\\_%'")
        banco = {(r["locale"], r["namespace"], r["key"]): r["value"] for r in rows}
        for nome, dominio in self.doc["domains"].items():
            for chave, termo in dominio["terms"].items():
                for loc in self.doc["locales"]:
                    valor = banco.get((loc, f"g_{nome}", chave))
                    if valor != termo["label"][loc]:
                        faltas.append(f"g_{nome}.{chave} [{loc}]: banco={valor!r}")
        self.assertEqual(faltas, [], "\n".join(faltas[:20]))

    def test_catalogo_do_banco_tem_rotulo_e_explicacao_em_toda_linha(self):
        """Nível 2: termo editorial vive no banco. Nenhuma linha pode chegar à tela sem nome e sem explicação."""
        faltas = []
        for tabela, spec in G.CATALOGS.items():
            with db_system() as c:
                rows = c.query(
                    f"SELECT code, {spec['label']} AS rotulo, {spec['explains']} AS explica FROM {tabela}")
            self.assertTrue(rows, f"{tabela} vazio — catálogo de referência não foi carregado")
            for r in rows:
                if not (r["rotulo"] or "").strip():
                    faltas.append(f"{tabela}.{r['code']}: sem {spec['label']}")
                if not (str(r["explica"] or "")).strip():
                    faltas.append(f"{tabela}.{r['code']}: sem {spec['explains']}")
        self.assertEqual(faltas, [], "\n".join(faltas))


class GlossaryOverHttpTests(unittest.TestCase):
    """v0.20.0 — a rota pública exercitada de ponta a ponta.

    O vocabulário era conferido contra o código e contra o banco, e NUNCA pelo HTTP. A rota é
    pública e sem autenticação: é justamente a que mais precisa ser atravessada por teste, porque
    é a única superfície do vocabulário que a interface consome.
    """

    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")

    def test_the_public_route_serves_the_official_vocabulary(self):
        r = self.c.get("/v1/public/glossary")
        self.assertEqual(r.status, 200, r)
        self.assertGreaterEqual(len(r.json["domains"]), 20)
        termos = {t["key"] for d in r.json["domains"] for t in d["terms"]}
        self.assertIn("substantiated", termos,
                      "o vocabulário da apuração de denúncia tem de sair pela rota pública")

    def test_a_single_domain_can_be_requested(self):
        r = self.c.get("/v1/public/glossary?domain=claim_status")
        self.assertEqual(r.status, 200, r)
        self.assertEqual([d["key"] for d in r.json["domains"]], ["claim_status"])

    def test_the_route_answers_in_the_requested_locale(self):
        r = self.c.get("/v1/public/glossary?locale=en")
        self.assertEqual(r.status, 200, r)
        rotulos = [t["label"] for d in r.json["domains"] for t in d["terms"]]
        self.assertTrue(rotulos, "nenhum rótulo devolvido")
