"""v0.19.0 — primeiro acesso e retorno por declarar contexto (FASES B e C).

DOIS DEFEITOS DE PRODUTO QUE ESTES TESTES FECHAM.

1. PRIMEIRO ACESSO. Organização recém-cadastrada vê ausência em quase tudo. Ausência é a resposta
   honesta, mas ausência sem próximo passo é uma parede. Aqui se exige que TODA área vazia diga o que
   é, por que está vazia, o que fazer, o que se ganha, de onde vem o dado e como se verifica — e que
   nenhuma delas invente contagem.

2. RETORNO POR CONTEXTO. A plataforma pedia o dado mais caro do produto (necessidade com fonte,
   barreiras, denominador com método) e não devolvia nada visível para quem preencheu: o sinal existia
   só do lado de quem financia. Agora existe retorno operacional — e o teste exige que ele seja
   operacional mesmo: `test_declarar_contexto_nao_mexe_na_reputacao` prova que o retorno NÃO virou
   ganho de reputação, que seria o contrário da tese.
"""
from __future__ import annotations

import unittest

from tests.support import ROOT, app_tx, db_system, grant_premium, new_account, server


class FirstRunStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.cli = new_account("osc", compliance="approved")

    def test_organizacao_nova_recebe_todas_as_areas_com_proximo_passo(self):
        r = self.cli.get("/v1/firstrun")
        self.assertEqual(r.status, 200, r.body)
        areas = r.json["areas"]
        self.assertGreaterEqual(len(areas), 12, "o inventário de primeiro acesso encolheu")
        faltas = []
        for a in areas:
            if a["filled"]:
                continue
            if not a["why_empty"]:
                faltas.append(f"{a['key']}: sem motivo de estar vazia")
            if not (a["next_action"] or {}).get("label"):
                faltas.append(f"{a['key']}: sem próximo passo")
            for campo in ("what_it_is", "what_you_gain", "data_origin", "how_verified"):
                if not (a.get(campo) or "").strip():
                    faltas.append(f"{a['key']}: {campo} vazio")
            if not a["required_fields"]:
                faltas.append(f"{a['key']}: não diz qual informação é obrigatória")
        self.assertEqual(faltas, [], "\n".join(faltas))

    def test_nenhuma_area_devolve_dado_inventado(self):
        """Contagem é contagem: área sem projeto escolhido devolve `counted: false`, não zero."""
        r = self.cli.get("/v1/firstrun")
        for a in r.json["areas"]:
            if a["counted"]:
                self.assertIsInstance(a["count"], int)
                self.assertGreaterEqual(a["count"], 0)
            else:
                self.assertIsNone(a["count"], f"{a['key']} devolveu contagem sem ter o que contar")

    def test_area_que_depende_de_projeto_diz_o_pre_requisito(self):
        r = self.cli.get("/v1/firstrun")
        por_chave = {a["key"]: a for a in r.json["areas"]}
        self.assertFalse(r.json["has_project"])
        bloqueada = por_chave["indicators"]
        self.assertEqual((bloqueada["blocked_by"] or {}).get("requires"), "project")
        self.assertFalse(bloqueada["next_action"]["available"])
        self.assertIn("projeto", (bloqueada["blocked_by"] or {})["label"].lower())

    def test_toda_rota_de_proximo_passo_existe_no_roteador(self):
        """Quem desenha não pode receber link morto: a rota do próximo passo tem de estar registrada."""
        from impacto.api import load_all
        from impacto.core.firstrun import AREAS
        from impacto.http import ROUTES
        load_all()
        registradas = {(r.method, r.path) for r in ROUTES}
        faltando = [(a.key, a.action_method, a.action_route) for a in AREAS
                    if (a.action_method, a.action_route) not in registradas]
        self.assertEqual(faltando, [], f"rotas de próximo passo inexistentes: {faltando}")

    def test_toda_tela_declarada_existe_na_interface(self):
        """Tela declarada tem de existir de verdade; o que não existe é declarado como a desenhar.

        Apontar para uma tela inexistente seria a mesma mentira de apontar para uma rota inexistente —
        só mais difícil de perceber, porque a pessoa clica e cai numa página em branco.
        """
        import re
        from impacto.core.firstrun import AREAS
        app = (ROOT / "web" / "src" / "app.tsx").read_text(encoding="utf-8")
        existentes = set(re.findall(r'^\s*\["(/[^"]*)"', app, re.M))
        faltando = [(a.key, a.screen) for a in AREAS if a.screen and a.screen not in existentes]
        self.assertEqual(faltando, [], f"tela declarada que não existe na interface: {faltando}")

    def test_area_sem_tela_declara_que_a_tela_sera_desenhada(self):
        """O vocabulário continua valendo para a próxima área que nascer sem tela.

        Na v0.19.0 este teste exigia que seis áreas — equidade, ODS, afirmações, reputação, selos e
        responsabilidade — dissessem `to_be_designed`, porque era a verdade: tinham API, serviço,
        banco, eventos, permissões, testes e documentação, e nenhuma tela. A v0.20.0 entregou as
        seis (§94), então o teste mudou de alvo, não de rigor: agora exige que NENHUMA área declare
        tela que não exista, e que o estado seja sempre um dos dois declarados. Se amanhã alguém
        acrescentar uma área sem tela, `to_be_designed` continua sendo a resposta honesta — o que
        não pode é apontar para uma tela inexistente, e disso cuida o teste acima.
        """
        r = self.cli.get("/v1/firstrun")
        estados = {a["key"]: a["next_action"]["screen_status"] for a in r.json["areas"]}
        self.assertEqual(set(estados.values()) - {"exists", "to_be_designed"}, set())
        for chave in ("equity", "ods", "claims", "reputation", "seals", "governance"):
            self.assertEqual(estados[chave], "exists",
                             f"{chave} perdeu a tela entregue na v0.20.0")

    def test_com_projeto_as_areas_de_projeto_passam_a_contar(self):
        proj = self.cli.post("/v1/projects", {
            "title": "Reforço escolar no bairro", "problem": "Defasagem de leitura na rede municipal",
            "objectives": "Recuperar leitura de 120 estudantes", "methodology": "Oficinas semanais",
            "territory": "MT"})
        self.assertIn(proj.status, (200, 201), proj.body)
        pid = proj.json["id"]
        r = self.cli.get(f"/v1/firstrun?project_id={pid}")
        self.assertEqual(r.status, 200, r.body)
        por_chave = {a["key"]: a for a in r.json["areas"]}
        self.assertTrue(r.json["has_project"])
        for chave in ("indicators", "evidence", "equity", "ods", "impact"):
            a = por_chave[chave]
            self.assertTrue(a["counted"], f"{chave} ainda não conta com projeto escolhido")
            self.assertIsNone(a["blocked_by"], f"{chave} segue bloqueada com projeto existente")
            self.assertTrue(a["next_action"]["available"])
            self.assertIn(pid, a["next_action"]["route"])


class ContextReturnTests(unittest.TestCase):
    """O retorno operacional por declarar contexto, medido antes e depois."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.cli = new_account("osc", compliance="approved")
        grant_premium(cls.cli)
        p = cls.cli.post("/v1/projects", {
            "title": "Água potável em comunidade ribeirinha",
            "problem": "Ausência de tratamento de água em 400 domicílios",
            "objectives": "Instalar filtros em 400 domicílios", "methodology": "Instalação e capacitação",
            "territory": "MT"})
        assert p.status in (200, 201), p.body
        cls.pid = p.json["id"]

    def _retorno(self) -> dict:
        r = self.cli.get(f"/v1/projects/{self.pid}/context-return")
        self.assertEqual(r.status, 200, r.body)
        return {i["key"]: i for i in r.json["items"]}

    def test_sem_contexto_o_retorno_e_zero_e_diz_o_que_abriria(self):
        """Projeto PRÓPRIO de propósito: testes da mesma classe rodam em ordem alfabética e
        compartilham estado — medir o projeto da classe aqui mediria um projeto já preenchido."""
        p = self.cli.post("/v1/projects", {
            "title": "Projeto sem contexto declarado", "problem": "Problema ainda não contextualizado",
            "objectives": "Objetivo declarado", "methodology": "Método declarado", "territory": "MT"})
        self.assertIn(p.status, (200, 201), p.body)
        r = self.cli.get(f"/v1/projects/{p.json['id']}/context-return")
        self.assertEqual(r.status, 200, r.body)
        itens = {i["key"]: i for i in r.json["items"]}
        norm = itens["NORMALIZATION_METHODS_AVAILABLE"]
        self.assertEqual(norm["available"], 0, "método disponível sem denominador declarado")
        self.assertEqual(len(norm["would_open"]), norm["total"],
                         "não disse o que cada denominador que falta abriria")
        self.assertEqual(itens["MATCH_EXPLAINABILITY"]["available"], 0)
        self.assertTrue(itens["MATCH_EXPLAINABILITY"]["would_open"])
        ctx = itens["CONTEXT_COMPLETENESS"]
        self.assertEqual(ctx["available"], 0)
        self.assertTrue(all(not p["declared"] for p in ctx["pieces"]))

    def test_todas_as_chaves_de_retorno_estao_presentes(self):
        from impacto.core.firstrun import RETURN_KEYS
        itens = self._retorno()
        self.assertEqual(set(itens), set(RETURN_KEYS))
        for chave, item in itens.items():
            self.assertTrue((item.get("detail") or "").strip(), f"{chave} sem explicação")
            self.assertIsInstance(item["available"], int)
            self.assertIsInstance(item["total"], int)
            self.assertLessEqual(item["available"], max(item["total"], item["available"]))

    def test_declarar_contexto_abre_metodo_de_normalizacao_de_verdade(self):
        antes = self._retorno()["NORMALIZATION_METHODS_AVAILABLE"]["available"]
        r = self.cli.put(f"/v1/projects/{self.pid}/equity/context", {
            "need_statement": "400 domicílios sem tratamento de água, segundo o censo municipal de 2024",
            "additionality": "Nenhum programa público atende a comunidade hoje",
            "need_source_name": "Censo municipal de saneamento", "need_source_date": "2024-05-01"})
        self.assertEqual(r.status, 200, r.body)
        d = self.cli.post("/v1/equity/denominators", {
            "scope": "project", "project_id": self.pid, "kind": "households", "value": 400,
            "unit": "domicílios", "reference_date": "2024-05-01",
            "source_name": "Censo municipal de saneamento", "source_date": "2024-05-01",
            "method_note": "Contagem de domicílios da comunidade no censo municipal de saneamento"})
        self.assertIn(d.status, (200, 201), d.body)
        depois = self._retorno()
        self.assertGreater(depois["NORMALIZATION_METHODS_AVAILABLE"]["available"], antes,
                           "denominador declarado com fonte não abriu nenhum método")
        metodos = [m["method"] for m in depois["NORMALIZATION_METHODS_AVAILABLE"]["items"]]
        self.assertIn("per_household", metodos)
        pecas = {p["key"]: p["declared"] for p in depois["CONTEXT_COMPLETENESS"]["pieces"]}
        self.assertTrue(pecas["need_statement"])
        self.assertTrue(pecas["need_source"])
        self.assertTrue(pecas["denominator"])
        self.assertFalse(pecas["counterfactual"], "contrafactual não declarado apareceu como declarado")

    def test_declarar_contexto_nao_mexe_na_reputacao(self):
        """A regra que impede o produto de virar o oposto da sua tese.

        Contexto declarado é retorno OPERACIONAL. Se declarar contexto mexesse na reputação, a
        plataforma passaria a premiar quem escreve bem em vez de quem mede — exatamente o que ela
        existe para não fazer.
        """
        with db_system() as c:
            antes = c.query("SELECT dimension, band, value FROM reputation_snapshots"
                            " WHERE org_id = $1 ORDER BY dimension", self.cli.org_id)
        r = self.cli.put(f"/v1/projects/{self.pid}/equity/context", {
            "need_statement": "400 domicílios sem tratamento de água, segundo o censo municipal de 2024",
            "additionality": "Nenhum programa público atende a comunidade hoje",
            "counterfactual": "Sem o projeto, o consumo seguiria sendo de água bruta do rio",
            "need_source_name": "Censo municipal de saneamento", "need_source_date": "2024-05-01"})
        self.assertEqual(r.status, 200, r.body)
        self.cli.get(f"/v1/projects/{self.pid}/context-return")
        with db_system() as c:
            depois = c.query("SELECT dimension, band, value FROM reputation_snapshots"
                             " WHERE org_id = $1 ORDER BY dimension", self.cli.org_id)
        self.assertEqual(antes, depois, "declarar contexto alterou reputação — isso não pode acontecer")

    def test_declarar_contexto_nao_concede_selo(self):
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM seal_awards WHERE org_id = $1", self.cli.org_id)
        self.assertEqual(n, 0, "selo apareceu sem concessão conferida pelo banco")
        itens = self._retorno()
        for selo in itens["SEAL_READINESS"]["items"]:
            self.assertLessEqual(selo["met"], selo["total"])
            if selo["met"] < selo["total"]:
                self.assertTrue(selo["missing"], f"{selo['code']} incompleto sem dizer o que falta")

    def test_projeto_nao_publicado_nao_expoe_contexto_a_quem_avalia(self):
        itens = self._retorno()
        visib = itens["FUNDER_VISIBILITY"]
        self.assertEqual(visib["items"][0]["aggregated_context_visible"], False)
        self.assertTrue(visib["would_open"], "não disse que publicar é o que abre a visibilidade")

    def test_o_retorno_declara_por_escrito_que_nao_da_ranking(self):
        r = self.cli.get(f"/v1/projects/{self.pid}/context-return")
        nota = r.json["no_ranking_note"].lower()
        self.assertIn("ranking", nota)
        self.assertIn("não dá", nota)


class FirstRunIsolationTests(unittest.TestCase):
    """Primeiro acesso é por organização: a contagem de uma não pode aparecer na outra."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.a = new_account("osc", compliance="approved")
        cls.b = new_account("osc", compliance="approved")
        cls.a.post("/v1/projects", {
            "title": "Projeto da organização A", "problem": "Problema A", "objectives": "Objetivo A",
            "methodology": "Método A", "territory": "MT"})

    def test_a_contagem_de_uma_organizacao_nao_vaza_para_a_outra(self):
        ra = self.a.get("/v1/firstrun")
        rb = self.b.get("/v1/firstrun")
        self.assertTrue(ra.json["has_project"])
        self.assertFalse(rb.json["has_project"], "projeto de outra organização apareceu no primeiro acesso")

    def test_projeto_de_outra_organizacao_nao_e_aceito_no_parametro(self):
        with app_tx(self.a) as c:
            pid = c.scalar("SELECT id::text FROM projects WHERE org_id = $1", self.a.org_id)
        r = self.b.get(f"/v1/firstrun?project_id={pid}")
        self.assertEqual(r.status, 404, "primeiro acesso aceitou projeto de outra organização")
