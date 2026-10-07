"""Duas travessias de ponta a ponta que a suíte provava em pedaços e ninguém percorria inteiras.

POR QUE ESTE ARQUIVO EXISTE

A matriz de jornadas por persona (`docs/execution/PERSONA_E2E_MATRIX.csv`) mostrou cinco passos da
persona de moderação com cobertura de ROTA e nenhuma de TRAVESSIA: manifestação do denunciado,
conclusão, medida, recurso e interruptor de emergência. Cada regra estava provada isoladamente — que
a conclusão exige fundamentação, que quem aplicou não julga o recurso, que o interruptor para a
escrita. O que ninguém percorria era o CAMINHO: denúncia → análise → contraditório → manifestação →
conclusão → medida → recurso → julgamento, com o estado de cada passo dependendo do anterior.

A diferença não é acadêmica. Uma regra passa isolada e falha em sequência quando o passo anterior
deixa o registro num estado que a regra não previu. É exatamente onde um processo de moderação
machuca alguém: não no teste da regra, e sim na ordem em que ela é aplicada.

O QUE ESTAS TRAVESSIAS NÃO AFIRMAM

Nada aqui homologa autoridade externa. `referral` registra ENCAMINHAMENTO, e o teste confere que o
texto não declara crime. Nenhuma denúncia deste arquivo descreve fato real, e o interruptor é
acionado contra o banco de teste — nunca contra produção.
"""
import unittest

from tests.support import (Client, db_system, grant_premium, make_admin, make_staff, new_account,
                           server)

#: Motivo longo o suficiente para os pisos do schema E do banco (10 a 20 caracteres, por rota).
FUNDAMENTO = ("Apuração concluída com base nas manifestações juntadas e nos documentos conferidos "
              "pela equipe de análise.")


def _liberar_interruptor():
    """Devolve a plataforma ao ar pelo HISTÓRICO, como o produto faz — não por UPDATE no estado."""
    with db_system() as c:
        for escopo in ("mutations", "logins", "uploads", "integrations", "maintenance"):
            if c.scalar("SELECT engaged FROM kill_switch_state WHERE scope = $1", escopo):
                c.run("INSERT INTO kill_switch_events(scope, action, reason) VALUES ($1,'release',$2)",
                      escopo, "limpeza automatica de teste de jornada")
    from impacto.core import killswitch
    killswitch.invalidate()


class FromComplaintToMeasureAndAppealTests(unittest.TestCase):
    """A travessia inteira da moderação, com as recusas no lugar onde elas realmente aparecem."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.denunciada = new_account("osc", compliance="approved")
        grant_premium(cls.denunciada)
        cls.denunciante = new_account("company", compliance="approved")
        cls.analista, _ = make_admin()
        # O segundo administrador não é conveniência de teste: o produto EXIGE que quem aplicou a
        # medida não julgue o recurso. Sem dois, o passo final não pode nem ser exercitado.
        cls.julgador, _ = make_admin()

    def test_a_travessia_completa_da_denuncia_ao_julgamento_do_recurso(self):
        denunciada, denunciante = self.denunciada, self.denunciante
        analista, julgador = self.analista, self.julgador

        # 1. Alguém denuncia. A denúncia por si não restringe nada.
        aberta = denunciante.post("/v1/reports", {
            "target_type": "organization", "target_id": denunciada.org_id, "reason": "incorrect_data",
            "category": "false_information",
            "details": "Dados de execução divulgados não correspondem às evidências publicadas."})
        self.assertIn(aberta.status, (200, 201), aberta.body)
        rid = aberta.json["id"]

        # 2. A medida AINDA NÃO pode citar esta denúncia: não há conclusão de procedência.
        cedo = analista.post("/v1/admin/enforcement", {
            "measure": "guidance", "target_org_id": denunciada.org_id, "report_id": rid,
            "rule_ref": "Termos de uso, veracidade das informações",
            "reason": "Tentativa de aplicar medida antes de concluir a apuração."})
        self.assertGreaterEqual(cedo.status, 400, f"medida citou denúncia sem conclusão: {cedo.body}")

        # 3. Tampouco cabe recurso: não há de quê recorrer.
        self.assertGreaterEqual(
            denunciada.post(f"/v1/conta/denuncias/{rid}/recurso",
                            {"note": "Recurso apresentado antes de qualquer conclusão da apuração."}).status,
            400)

        # 4. A plataforma leva para análise e abre o contraditório.
        self.assertIn(analista.post(f"/v1/admin/reports/{rid}/review").status, (200, 201))
        self.assertIn(analista.post(f"/v1/admin/reports/{rid}/request-response", {
            "question": "Apresente as evidências de execução correspondentes ao período divulgado."
        }).status, (200, 201))

        # 5. A denunciada vê o que lhe é imputado — e NÃO vê quem denunciou.
        minhas = denunciada.get("/v1/conta/denuncias")
        self.assertEqual(minhas.status, 200, minhas.body)
        texto = str(minhas.json)
        self.assertIn(rid, texto)
        for vazado in (denunciante.org_id, denunciante.email):
            self.assertNotIn(vazado, texto, "a identidade de quem denunciou apareceu para a denunciada")

        # 6. Outra organização não responde pela denunciada.
        self.assertGreaterEqual(
            denunciante.post(f"/v1/conta/denuncias/{rid}/manifestacao",
                             {"body": "Manifestação enviada por quem não é a organização denunciada."}).status,
            400)

        # 7. A denunciada se manifesta, e a plataforma lê.
        self.assertIn(denunciada.post(f"/v1/conta/denuncias/{rid}/manifestacao", {
            "body": "Juntamos o relatório de execução e as notas fiscais do período questionado."
        }).status, (200, 201))
        respostas = analista.get(f"/v1/admin/reports/{rid}/responses")
        self.assertEqual(respostas.status, 200, respostas.body)
        self.assertTrue(respostas.json["items"], "a manifestação não chegou à apuração")

        # 8. Conclusão: sem fundamentação, recusada; com fundamentação, registrada.
        self.assertGreaterEqual(
            analista.post(f"/v1/admin/reports/{rid}/conclude",
                          {"finding": "substantiated", "rationale": "curto"}).status, 400)
        fim = analista.post(f"/v1/admin/reports/{rid}/conclude",
                            {"finding": "substantiated", "rationale": FUNDAMENTO})
        self.assertIn(fim.status, (200, 201), fim.body)

        # 9. Agora a medida pode citar a denúncia — e começa pelo primeiro degrau da escada.
        medida = analista.post("/v1/admin/enforcement", {
            "measure": "guidance", "target_org_id": denunciada.org_id, "report_id": rid,
            "rule_ref": "Termos de uso, veracidade das informações",
            "reason": "Orientação para corrigir a divulgação e republicar com as evidências conferidas."})
        self.assertIn(medida.status, (200, 201), medida.body)
        aid = medida.json["id"]
        self.assertFalse(medida.json["escalation_override"],
                         "o primeiro degrau não deveria exigir contorno da escada")

        # 10. Recorrer da CONCLUSÃO e contestar a MEDIDA são dois atos distintos, e a travessia
        #     precisa dos dois: o recurso ataca a apuração, a contestação ataca a sanção. A primeira
        #     versão deste teste confundiu os dois e julgou uma contestação que nunca foi aberta.
        self.assertIn(denunciada.post(f"/v1/conta/denuncias/{rid}/recurso", {
            "note": "Recorremos: as evidências juntadas cobrem o período apontado na denúncia."
        }).status, (200, 201))
        minhas_medidas = denunciada.get("/v1/conta/moderacao")
        self.assertEqual(minhas_medidas.status, 200, minhas_medidas.body)
        self.assertIn(aid, [m["id"] for m in minhas_medidas.json["items"]])
        contesta = denunciada.post(f"/v1/conta/moderacao/{aid}/contestar", {
            "note": "Contestamos a medida: a divulgação foi corrigida antes da orientação."})
        self.assertIn(contesta.status, (200, 201), contesta.body)
        self.assertEqual(contesta.json["status"], "under_appeal")

        # 11. Contestar NÃO suspende a medida. Quem contesta segue sob ela até o julgamento, e isso
        #     é decisão de produto declarada em `ENF.ACTIVE_STATUSES` — não efeito colateral.
        from impacto.network import enforcement as ENF
        self.assertIn("under_appeal", ENF.ACTIVE_STATUSES,
                      "contestar passou a suspender a medida; a contestação não é liminar")

        # 12. Contesta-se uma vez por medida.
        self.assertGreaterEqual(
            denunciada.post(f"/v1/conta/moderacao/{aid}/contestar",
                            {"note": "Segunda contestação da mesma medida, que não deve ser aceita."}).status,
            400)

        # 13. Quem aplicou não julga. Quem julga é outro.
        proprio = analista.post(f"/v1/admin/enforcement/{aid}/appeal-decision", {
            "uphold": True, "note": "Tentativa de julgar o próprio ato."})
        self.assertGreaterEqual(proprio.status, 400, f"quem aplicou julgou o próprio ato: {proprio.body}")
        julgado = julgador.post(f"/v1/admin/enforcement/{aid}/appeal-decision", {
            "uphold": False, "note": "Contestação acolhida: as evidências juntadas cobrem o período."})
        self.assertIn(julgado.status, (200, 201), julgado.body)

        # 14. O histórico é o que torna a proporcionalidade verificável.
        hist = julgador.get(f"/v1/admin/enforcement/history?org_id={denunciada.org_id}")
        self.assertEqual(hist.status, 200, hist.body)
        self.assertIn(aid, [x["id"] for x in hist.json["items"]])
        self.assertIn("next_allowed", hist.json)

    def test_o_encaminhamento_a_autoridade_nao_declara_crime(self):
        """`referral` é dever de comunicar, não juízo penal — e o texto do produto precisa dizer isso."""
        from impacto.network import enforcement as ENF
        self.assertIn("referral", ENF.MEASURES)
        efeito = ENF.EFFECT["referral"].lower()
        self.assertIn("não é punição", efeito)
        for proibido in ("crime comprovado", "culpado", "condenado"):
            self.assertNotIn(proibido, efeito)


class TheEmergencySwitchJourneyTests(unittest.TestCase):
    """A travessia do incidente: parar a escrita, continuar vendo, e voltar ao ar."""

    @classmethod
    def setUpClass(cls):
        server()
        # `security.kill_switch` é `super_admin_only` e NENHUM papel de equipe a recebe — nem
        # `security`, que tem chaves e auditoria. Parar a plataforma é do papel mais alto, e a
        # migração 0052 explica por quê. A primeira versão deste teste usou `make_staff("security")`
        # e tomou 403: o produto estava certo, o teste é que presumia uma delegação que não existe.
        cls.seguranca, _ = make_admin()
        cls.equipe_de_seguranca = make_staff("security")
        cls.org = new_account("osc", compliance="approved")
        grant_premium(cls.org)

    def setUp(self):
        _liberar_interruptor()
        self.addCleanup(_liberar_interruptor)

    def test_a_travessia_do_incidente_para_escrever_continuar_vendo_e_voltar(self):
        seg, org = self.seguranca, self.org

        # 1. Estado inicial: nada parado, e cada escopo diz o que faz.
        antes = seg.get("/v1/admin/kill-switch")
        self.assertEqual(antes.status, 200, antes.body)
        escopos = {e["scope"]: e for e in antes.json["scopes"]}
        self.assertEqual(set(escopos), {"mutations", "logins", "uploads", "integrations", "maintenance"})
        self.assertFalse(any(e["engaged"] for e in escopos.values()))
        for e in escopos.values():
            self.assertTrue(e["effect"], f"escopo {e['scope']} sem efeito declarado")

        # 2. Nem o papel de segurança da equipe alcança o interruptor: é do super-administrador.
        negado = self.equipe_de_seguranca.get("/v1/admin/kill-switch")
        self.assertEqual(negado.status, 403, negado.body)
        self.assertEqual(negado.json["details"]["required_permission"], "security.kill_switch")

        # 3. A escrita funciona antes do incidente.
        livre = org.post("/v1/projects", {"title": "Projeto antes do incidente", "problem": "Problema declarado",
                                          "objectives": "Objetivo declarado", "methodology": "Método declarado",
                                          "territory": "MT"})
        self.assertIn(livre.status, (200, 201), livre.body)

        # 4. Aciona.
        liga = seg.post("/v1/admin/kill-switch", {
            "scope": "mutations", "action": "engage",
            "reason": "Incidente simulado em teste automatizado de jornada."})
        self.assertIn(liga.status, (200, 201), liga.body)
        self.assertTrue(liga.json["engaged"])

        # 5. A escrita para.
        barrada = org.post("/v1/projects", {"title": "Projeto durante o incidente", "problem": "Problema declarado",
                                            "objectives": "Objetivo declarado", "methodology": "Método declarado",
                                            "territory": "MT"})
        self.assertGreaterEqual(barrada.status, 400, f"a escrita passou com o interruptor acionado: {barrada.body}")

        # 6. A leitura não para: cegar quem investiga serve ao atacante.
        self.assertEqual(org.get("/v1/projects").status, 200)

        # 7. O vidro quebrado: a própria rota do interruptor continua acessível, ou ninguém o desliga.
        self.assertEqual(seg.get("/v1/admin/kill-switch").status, 200)

        # 8. O público sabe O QUE está suspenso, nunca o POR QUÊ.
        publico = Client().get("/v1/meta/platform-status")
        self.assertEqual(publico.status, 200, publico.body)
        self.assertNotIn("Incidente simulado", str(publico.json),
                         "o motivo do incidente vazou para a rota pública")

        # 9. Libera, e a escrita volta.
        solta = seg.post("/v1/admin/kill-switch", {
            "scope": "mutations", "action": "release", "reason": "Fim do incidente simulado em teste."})
        self.assertIn(solta.status, (200, 201), solta.body)
        self.assertFalse(solta.json["engaged"])
        volta = org.post("/v1/projects", {"title": "Projeto depois do incidente", "problem": "Problema declarado",
                                          "objectives": "Objetivo declarado", "methodology": "Método declarado",
                                          "territory": "MT"})
        self.assertIn(volta.status, (200, 201), volta.body)

        # 10. Os dois eventos ficaram no histórico, com motivo.
        depois = seg.get("/v1/admin/kill-switch")
        acoes = [h for h in depois.json["history"] if h.get("scope") == "mutations"]
        self.assertGreaterEqual(len(acoes), 2, f"histórico não registrou o incidente: {acoes}")
        self.assertTrue(all(h.get("reason") for h in acoes), "evento do interruptor sem motivo registrado")
