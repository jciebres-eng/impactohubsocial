"""v0.20.0 — denúncia, suspeita, infração comprovada e consequência jurídica (ETAPA 2).

A PERGUNTA DESCONFORTÁVEL QUE ESTES TESTES RESPONDEM

Um produto que mede reputação e aplica sanção precisa responder: o que impede que denunciar vire uma
arma? Até a v0.19.0 a resposta era frágil. Três caminhos existiam, e dois tinham defeito:

1. a denúncia não tocava a reputação — correto, e agora travado por teste;
2. uma denúncia ABERTA já elevava o risco de conformidade da organização (`compliance.py` contava
   denúncias abertas e devolvia `warning`, que vira `organizations.compliance_risk`) — ou seja,
   bastava acusar para causar efeito;
3. `enforcement_actions.report_id` aceitava QUALQUER denúncia, inclusive recém-aberta: o banco
   permitia aplicar sanção a partir de acusação não apurada.

E havia um quarto problema, de direção oposta: a escada de dez degraus era aplicada, notificada e
contestável — e **não restringia nada**. `active_for()` nunca era chamada. Uma suspensão temporária
era um aviso bonito: a organização suspensa continuava publicando, propondo e se candidatando.

Os testes abaixo cobrem os quatro pontos, mais o direito de resposta, que não existia.
"""
from __future__ import annotations

import unittest

from tests.support import Client, db_system, grant_premium, make_admin, new_account, server


def _denunciar(denunciante: Client, alvo_org: str, **extra) -> str:
    r = denunciante.post("/v1/reports", {
        "target_type": "organization", "target_id": alvo_org, "reason": "fraud",
        "details": "Indício de prestação de contas inexistente no projeto divulgado.", **extra})
    assert r.status in (200, 201), r.body
    return r.json["id"]


class VocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.cli = new_account("osc", compliance="approved")

    def test_os_quatro_niveis_sao_declarados_pela_api(self):
        r = self.cli.get("/v1/reports/vocabulary")
        self.assertEqual(r.status, 200, r.body)
        niveis = {n["key"]: n for n in r.json["levels"]}
        self.assertEqual(set(niveis), {"report", "suspicion", "substantiated", "legal_referral"})
        self.assertIn("nenhum", niveis["report"]["effects"].lower())
        self.assertIn("ÚNICO", niveis["substantiated"]["effects"])
        for termo in ("polícia", "Ministério Público", "Judiciário"):
            self.assertIn(termo, niveis["legal_referral"]["effects"])

    def test_arquivar_e_concluir_pela_improcedencia_sao_coisas_diferentes(self):
        r = self.cli.get("/v1/reports/vocabulary")
        situacoes = {s["key"]: s["label"] for s in r.json["statuses"]}
        self.assertIn("dismissed", situacoes)
        self.assertIn("unsubstantiated", situacoes)
        self.assertNotEqual(situacoes["dismissed"], situacoes["unsubstantiated"])
        self.assertIn("sem análise de mérito", situacoes["dismissed"])

    def test_as_categorias_do_codigo_sao_as_do_banco(self):
        """Havia duas listas de doze categorias, com cinco diferentes. Agora é uma só."""
        import re

        from impacto.network import enforcement as ENF
        with db_system() as c:
            definicao = c.scalar("SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                                 " WHERE conrelid = 'reports'::regclass AND conname = 'reports_category_check'")
        no_banco = set(re.findall(r"'([a-z_]+)'", definicao))
        no_codigo = {k for k, _ in ENF.CATEGORIES}
        self.assertEqual(no_codigo, no_banco,
                         f"divergência: só no código {no_codigo - no_banco}, só no banco {no_banco - no_codigo}")


class ReportHasNoEffectByItselfTests(unittest.TestCase):
    """Nível 1: uma denúncia, sozinha, não produz efeito nenhum."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.alvo = new_account("osc", compliance="approved")
        cls.denunciante = new_account("company", compliance="approved")
        cls.report_id = _denunciar(cls.denunciante, cls.alvo.org_id, category="unethical_conduct")

    def test_a_denuncia_nao_restringe_nenhuma_capacidade(self):
        from impacto.network import enforcement as ENF
        with db_system() as c:
            self.assertEqual(ENF.restrictions(c, org_id=self.alvo.org_id), {},
                             "a denúncia restringiu alguma capacidade")

    def test_a_denuncia_nao_aparece_na_reputacao(self):
        r = self.alvo.get("/v1/reputation/me")
        self.assertEqual(r.status, 200, r.body)
        # Os insumos de cada dimensão são declarados: nenhum deles pode citar denúncia, medida ou
        # risco. (Conferir o texto cru não serve: "reported_values" é um insumo legítimo de medição.)
        proibidos = {"reports", "report_count", "denuncias", "enforcement", "measures", "sanctions",
                     "risk_signals", "risk_level"}
        for d in r.json["dimensions"]:
            vazou = proibidos & set(d["inputs"])
            self.assertEqual(vazou, set(), f"{d['dimension']} passou a ler {vazou}")
        self.assertNotIn("denúncia", r.json["no_automatic_decision"].lower())

    def test_a_denuncia_aberta_nao_eleva_o_risco_de_conformidade(self):
        """O defeito mais perigoso que esta etapa corrigiu: acusar bastava para piorar o risco."""
        from impacto.services import compliance as COMP
        with db_system() as c:
            out = COMP.run_checks(c, self.alvo.org_id, actor=None)
        check = next(x for x in out["checks"] if x["check_type"] == "substantiated_reports")
        self.assertEqual(check["status"], "pass",
                         "denúncia em apuração ainda pesa na conformidade")
        self.assertEqual(check["details"]["substantiated"], 0)
        self.assertGreaterEqual(check["details"]["under_review"], 1,
                                "a denúncia em apuração deveria ao menos ser informada")

    def test_o_denunciado_nao_ve_a_denuncia_antes_de_ser_chamado(self):
        r = self.alvo.get("/v1/conta/denuncias")
        self.assertEqual(r.status, 200, r.body)
        self.assertEqual(r.json["items"], [],
                         "o denunciado viu a denúncia antes de o contraditório ser aberto")

    def test_a_organizacao_nao_denuncia_a_si_mesma(self):
        r = self.alvo.post("/v1/reports", {
            "target_type": "organization", "target_id": self.alvo.org_id, "reason": "other",
            "details": "tentativa de denunciar a si mesma"})
        self.assertEqual(r.status, 422, r.body)


class MeasureRequiresSubstantiationTests(unittest.TestCase):
    """Nível 3: só infração comprovada autoriza medida — e quem recusa é o banco."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.alvo = new_account("osc", compliance="approved")
        cls.denunciante = new_account("company", compliance="approved")
        cls.report_id = _denunciar(cls.denunciante, cls.alvo.org_id)
        cls.admin, _ = make_admin()

    def test_o_banco_recusa_medida_apoiada_em_denuncia_sem_conclusao(self):
        # Denúncia PRÓPRIA: a da classe é concluída por outro teste, e testes de uma classe rodam em
        # ordem alfabética compartilhando estado.
        rid = _denunciar(self.denunciante, self.alvo.org_id)
        with db_system() as c:
            quem = c.scalar("SELECT id::text FROM users WHERE is_platform_admin ORDER BY created_at LIMIT 1")
            with self.assertRaises(Exception) as erro:
                c.run("INSERT INTO enforcement_actions(target_org_id, report_id, measure, severity,"
                      " rule_ref, reason, decided_by) VALUES ($1,$2,'warning',2,'regra 1',"
                      " 'motivo suficientemente longo para o check', $3)",
                      self.alvo.org_id, rid, quem)
        self.assertIn("sem conclusão de procedência", str(erro.exception))

    def test_depois_da_conclusao_de_procedencia_a_medida_e_aceita(self):
        r1 = self.admin.post(f"/v1/admin/reports/{self.report_id}/review", {})
        self.assertEqual(r1.status, 200, r1.body)
        r2 = self.admin.post(f"/v1/admin/reports/{self.report_id}/conclude", {
            "finding": "substantiated",
            "rationale": "Análise concluiu que a prestação de contas divulgada não corresponde ao registrado."})
        self.assertEqual(r2.status, 200, r2.body)
        self.assertTrue(r2.json["authorizes_measure"])
        with db_system() as c:
            quem = c.scalar("SELECT id::text FROM users WHERE is_platform_admin ORDER BY created_at LIMIT 1")
            c.run("INSERT INTO enforcement_actions(target_org_id, report_id, measure, severity,"
                  " rule_ref, reason, decided_by) VALUES ($1,$2,'warning',2,'regra 1',"
                  " 'motivo suficientemente longo para o check', $3)",
                  self.alvo.org_id, self.report_id, quem)
            n = c.scalar("SELECT count(*) FROM enforcement_actions WHERE report_id = $1", self.report_id)
        self.assertEqual(n, 1)

    def test_a_conclusao_exige_fundamentacao(self):
        rid = _denunciar(self.denunciante, self.alvo.org_id)
        self.admin.post(f"/v1/admin/reports/{rid}/review", {})
        r = self.admin.post(f"/v1/admin/reports/{rid}/conclude",
                            {"finding": "substantiated", "rationale": "curto"})
        self.assertEqual(r.status, 422, r.body)

    def test_a_conclusao_nao_se_reescreve_em_silencio(self):
        rid = _denunciar(self.denunciante, self.alvo.org_id)
        self.admin.post(f"/v1/admin/reports/{rid}/review", {})
        self.admin.post(f"/v1/admin/reports/{rid}/conclude", {
            "finding": "unsubstantiated",
            "rationale": "A análise não encontrou elementos que sustentem o que foi relatado."})
        with db_system() as c:
            with self.assertRaises(Exception) as erro:
                c.run("UPDATE reports SET finding = 'substantiated' WHERE id = $1", rid)
        self.assertIn("só muda por recurso", str(erro.exception))

    def test_arquivar_nao_grava_conclusao(self):
        rid = _denunciar(self.denunciante, self.alvo.org_id)
        r = self.admin.post(f"/v1/admin/reports/{rid}/dismiss",
                            {"rationale": "Relato duplicado de outra denúncia já registrada no sistema."})
        self.assertEqual(r.status, 200, r.body)
        with db_system() as c:
            linha = c.one("SELECT status, finding FROM reports WHERE id = $1", rid)
        self.assertEqual(linha["status"], "dismissed")
        self.assertIsNone(linha["finding"], "arquivar gravou conclusão — arquivar não é absolver")


class RightOfResponseTests(unittest.TestCase):
    """Nível 2: o denunciado é ouvido ANTES da conclusão, e nunca vê quem denunciou.

    Cada teste abre a PRÓPRIA denúncia: testes de uma classe rodam em ordem alfabética e compartilham
    estado, e aqui cada passo muda a situação da denúncia — compartilhar uma só faria cada teste medir
    o estado deixado pelo anterior.
    """

    @classmethod
    def setUpClass(cls):
        server()
        cls.alvo = new_account("osc", compliance="approved")
        cls.denunciante = new_account("company", compliance="approved")
        cls.admin, _ = make_admin()

    def _em_contraditorio(self) -> str:
        rid = _denunciar(self.denunciante, self.alvo.org_id, category="non_payment")
        r = self.admin.post(f"/v1/admin/reports/{rid}/request-response", {
            "question": "Pedimos que a organização informe como foi feita a prestação de contas citada."})
        self.assertEqual(r.status, 200, r.body)
        return rid

    def test_o_denunciado_passa_a_ver_o_que_lhe_e_imputado(self):
        rid = self._em_contraditorio()
        r = self.alvo.get("/v1/conta/denuncias")
        self.assertEqual(r.status, 200, r.body)
        item = next((i for i in r.json["items"] if i["id"] == rid), None)
        self.assertIsNotNone(item, r.body)
        self.assertTrue(item["can_respond"])
        self.assertEqual(item["category"], "non_payment")

    def test_a_visao_do_denunciado_nunca_revela_quem_denunciou(self):
        self._em_contraditorio()
        r = self.alvo.get("/v1/conta/denuncias")
        texto = r.body.decode("utf-8", "ignore")
        self.assertNotIn("reporter", texto)
        self.assertNotIn(self.denunciante.org_id, texto)
        self.assertNotIn(self.denunciante.user["id"], texto)

    def test_a_manifestacao_e_registrada_e_devolve_a_denuncia_para_analise(self):
        rid = self._em_contraditorio()
        r = self.alvo.post(f"/v1/conta/denuncias/{rid}/manifestacao", {
            "body": "A prestação de contas foi enviada ao financiador em janeiro, com comprovantes."})
        self.assertIn(r.status, (200, 201), r.body)
        with db_system() as c:
            linha = c.one("SELECT id::text AS id, body FROM report_responses WHERE report_id = $1", rid)
            situacao = c.scalar("SELECT status FROM reports WHERE id = $1", rid)
            with self.assertRaises(Exception):
                c.run("UPDATE report_responses SET body = 'reescrito' WHERE id = $1", linha["id"])
        self.assertIn("comprovantes", linha["body"])
        self.assertEqual(situacao, "under_review",
                         "a manifestação não devolveu a denúncia para análise")

    def test_outra_organizacao_nao_responde_pela_denunciada(self):
        rid = self._em_contraditorio()
        outra = new_account("osc", compliance="approved")
        r = outra.post(f"/v1/conta/denuncias/{rid}/manifestacao",
                       {"body": "tentativa de manifestação por organização que não é alvo"})
        self.assertEqual(r.status, 404, r.body)

    def test_cabe_recurso_da_conclusao(self):
        rid = self._em_contraditorio()
        c1 = self.admin.post(f"/v1/admin/reports/{rid}/conclude", {
            "finding": "substantiated",
            "rationale": "A manifestação não demonstrou o envio da prestação de contas citada."})
        self.assertEqual(c1.status, 200, c1.body)
        r = self.alvo.post(f"/v1/conta/denuncias/{rid}/recurso", {
            "note": "Anexamos o protocolo de envio da prestação de contas ao financiador."})
        self.assertEqual(r.status, 200, r.body)
        self.assertEqual(r.json["status"], "appealed")

    def test_nao_se_recorre_do_que_nao_foi_concluido(self):
        rid = self._em_contraditorio()
        r = self.alvo.post(f"/v1/conta/denuncias/{rid}/recurso",
                           {"note": "tentativa de recorrer antes de existir qualquer conclusão"})
        self.assertEqual(r.status, 409, r.body)


class LegalReferralTests(unittest.TestCase):
    """Nível 4: a plataforma encaminha, não julga."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.alvo = new_account("osc", compliance="approved")
        cls.denunciante = new_account("company", compliance="approved")
        cls.admin, _ = make_admin()

    def test_encaminhar_exige_dizer_por_que(self):
        rid = _denunciar(self.denunciante, self.alvo.org_id)
        self.admin.post(f"/v1/admin/reports/{rid}/review", {})
        r = self.admin.post(f"/v1/admin/reports/{rid}/conclude", {
            "finding": "substantiated", "rationale": "A análise encontrou indício documental relevante.",
            "legal_referral": True, "legal_referral_note": "curto"})
        self.assertEqual(r.status, 422, r.body)

    def test_o_encaminhamento_nao_declara_crime(self):
        rid = _denunciar(self.denunciante, self.alvo.org_id)
        self.admin.post(f"/v1/admin/reports/{rid}/review", {})
        r = self.admin.post(f"/v1/admin/reports/{rid}/conclude", {
            "finding": "substantiated",
            "rationale": "A análise encontrou indício documental que excede a competência da plataforma.",
            "legal_referral": True,
            "legal_referral_note": "O caso envolve possível uso indevido de recurso público e foge do que a plataforma apura."})
        self.assertEqual(r.status, 200, r.body)
        self.assertTrue(r.json["legal_referral"])
        self.assertIn("NÃO declara crime", r.json["legal_note"])
        texto = r.body.decode("utf-8", "ignore").lower()
        self.assertNotIn("crime comprovado", texto)
        self.assertNotIn("culpado", texto)


class MeasuresNowRestrictTests(unittest.TestCase):
    """O outro lado: a medida passa a RESTRINGIR de verdade."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc", compliance="approved")
        grant_premium(cls.org)
        cls.admin, _ = make_admin()
        p = cls.org.post("/v1/projects", {
            "title": "Projeto sob medida", "problem": "Problema declarado",
            "objectives": "Objetivo declarado", "methodology": "Método declarado", "territory": "MT"})
        assert p.status in (200, 201), p.body
        cls.pid = p.json["id"]
        # A medida entra aqui, e não dentro de um teste: testes de uma classe rodam em ORDEM
        # ALFABÉTICA e compartilham estado, então aplicar no meio faria os outros medirem um estado
        # que depende do nome do método.
        r = cls.admin.post("/v1/admin/enforcement", {
            "measure": "temporary_suspension", "target_org_id": cls.org.org_id,
            "rule_ref": "Termos de uso, cláusula de prestação de contas",
            "reason": "Medida aplicada no cenário de teste para conferir que a restrição vale de verdade.",
            "ends_at": "2027-01-01T00:00:00-03:00",
            "override_reason": "Cenário de teste exige o degrau sem histórico anterior para medir o efeito."})
        assert r.status in (200, 201), r.body

    def test_os_tres_primeiros_degraus_nao_restringem_de_proposito(self):
        from impacto.network import enforcement as ENF
        for medida in ("guidance", "warning", "formal_notice"):
            self.assertEqual(ENF.RESTRICTS[medida], (),
                             f"{medida} restringe algo; os três primeiros degraus existem para "
                             "dizer o que mudar ANTES de restringir")

    def test_suspensao_temporaria_impede_publicar_projeto(self):
        pub = self.org.post(f"/v1/projects/{self.pid}/publish", {})
        self.assertEqual(pub.status, 423, pub.body)
        self.assertEqual(pub.json["code"], "restricted_by_measure")
        self.assertIn("rule_ref", str(pub.json))

    def test_a_restricao_diz_qual_medida_qual_regra_e_ate_quando(self):
        from impacto.network import enforcement as ENF
        with db_system() as c:
            atual = ENF.restrictions(c, org_id=self.org.org_id)
        self.assertIn("publish_project", atual)
        item = atual["publish_project"]
        self.assertEqual(item["measure"], "temporary_suspension")
        self.assertTrue(item["rule_ref"])
        self.assertIsNotNone(item["ends_at"])

    def test_contestar_nao_destrava_a_medida(self):
        """Se contestar suspendesse o efeito, bastaria contestar para destravar."""
        from impacto.network import enforcement as ENF
        self.assertIn("under_appeal", ENF.ACTIVE_STATUSES)
        self.assertIn("upheld", ENF.ACTIVE_STATUSES)
        self.assertNotIn("overturned", ENF.ACTIVE_STATUSES)
        self.assertNotIn("lifted", ENF.ACTIVE_STATUSES)

    def test_a_medida_vencida_e_encerrada_por_trabalho_agendado(self):
        """`expire_due()` existia desde a v0.16.0 e nunca era chamada: a situação `expired` jamais
        era atingida, e uma suspensão "de 30 dias" valia para sempre."""
        from impacto import jobs
        nomes = {nome for nome, _fn in jobs.JOBS}
        self.assertIn("enforcement_expiry", nomes,
                      "o encerramento de medida vencida não está no ciclo do executor")


class ReputationStaysCleanTests(unittest.TestCase):
    """A trava que impede o produto de virar máquina de acusação."""

    def test_a_reputacao_nunca_le_denuncia_sancao_ou_risco(self):
        from tests.support import ROOT
        fonte = (ROOT / "backend" / "impacto" / "impact" / "reputation.py").read_text(encoding="utf-8")
        for tabela in ("reports", "enforcement_actions", "risk_signals", "risk_assessments",
                       "report_responses", "org_blocks"):
            self.assertNotIn(tabela, fonte,
                             f"a reputação passou a ler {tabela} — denúncia não pode virar nota")

    def test_as_dimensoes_declaram_que_nao_leem_denuncia(self):
        from impacto.impact import reputation as REP
        self.assertIn("NO_AUTOMATIC_DECISION_NOTE", dir(REP))
        self.assertIn("não", REP.NO_AUTOMATIC_DECISION_NOTE.lower())
