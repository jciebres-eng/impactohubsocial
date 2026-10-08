"""v0.26.0 — CONTRATO COMO REGRA OPERACIONAL e INTEGRIDADE FINANCEIRA, provados pela API.

O que estes testes provam:
  * um acordo de financiamento de R$ 100.000 com taxa de serviço de 3% contratada produz, ao ficar
    vigente, uma matriz de distribuição rastreável — contrato (hash), regra comercial, versão de preço,
    linhas, hash da matriz, lançamento no livro do projeto — e NENHUM valor aparece do nada;
  * a taxa só vira cobrança quando a regra comercial está ATIVA (carta legal verde); desligada, fica
    registrada como não cobrável, com o motivo. Nos dois casos a plataforma não custodia nada;
  * GMV (valor contratado) ≠ receita da plataforma (a taxa cobrável);
  * obrigações derivadas: quem entrega, quem aceita em quanto tempo (política do acordo), quem paga;
  * quem entrega não aceita a própria entrega (quatro olhos no banco);
  * contrato alterado depois de aprovado → NOVA VERSÃO em rascunho; a anterior fica substituída e as
    assinaturas antigas deixam de aprovar;
  * ativação duplicada não produz efeito duplicado; outra organização não enxerga a matriz.
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
import unittest

from tests.support import ADMIN_URL, DB_NAME, PASSWORD, db_system, last_signature_code, new_account, server
from tests.test_v0140_trust import upload


def _d(dias: int) -> str:
    return (dt.date.today() + dt.timedelta(days=dias)).isoformat()


class ContractRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.funder = new_account("company", compliance="approved")
        cls.outra = new_account("company", compliance="approved")
        pr = cls.osc.post("/v1/projects", {"title": "Projeto do acordo v0.26", "summary": "Projeto para o contrato operacional.",
                                           "causes": ["educacao"], "territory": "BR-MT", "ods": [4], "beneficiaries_count": 40,
                                           "budget_total_cents": 10_000_000})
        assert pr.status == 201, pr
        cls.project = pr.json["id"]

    # ---------------------------------------------------------------- apoio
    # v0.27.0: no acordo de FINANCIAMENTO o percentual vem do catálogo versionado (3,5% em 2027.01), nunca do pedido.
    # Os testes desta rodada passaram a conferir 3,5%; o modo (deducted/additional) continua cláusula do contrato.
    FEE_BPS = 350

    def _acordo(self, *, fee_mode="additional", value=10_000_000, review_days=10, calendar="calendar"):
        doc = upload(self.osc, name="acordo-financiamento.txt", body=b"Acordo de financiamento - versao 1", doc_type="contrato")
        r = self.osc.post("/v1/signed-agreements", {
            "kind": "funding", "title": "Financiamento do projeto", "summary": "Aporte em 2 marcos com taxa de serviço contratada.",
            "document_id": doc, "project_id": self.project, "value_cents": value,
            "fee_mode": fee_mode, "review_days": review_days, "calendar_type": calendar})
        self.assertEqual(r.status, 201, r)
        aid = r.json["id"]
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/parties", {"org_id": self.funder.org_id, "role": "funder"}).status, 201)
        for seq, (titulo, valor, dias) in enumerate((("Compra dos instrumentos", value // 2, 30), ("Primeiro semestre de aulas", value - value // 2, 200)), 1):
            m = self.osc.post(f"/v1/signed-agreements/{aid}/milestones", {"title": titulo, "due_on": _d(dias), "seq": seq, "amount_cents": valor})
            self.assertEqual(m.status, 201, m)
        return aid

    def _assinar(self, aid, *clientes):
        for c in clientes:
            self.assertEqual(c.post("/v1/signatures/challenge", {"subject_type": "agreement", "subject_id": aid}).status, 201)
            r = c.post(f"/v1/signed-agreements/{aid}/sign", {"statement": "Assino este acordo e me responsabilizo pelo combinado.",
                                                              "password": PASSWORD, "code": last_signature_code(c.email)})
            self.assertEqual(r.status, 200, r)
        return r.json["agreement_status"]

    # ---------------------------------------------------------------- 1. integridade financeira
    def test_100k_with_3_percent_is_traceable_end_to_end_and_the_platform_holds_nothing(self):
        aid = self._acordo()
        pub = self.osc.post(f"/v1/signed-agreements/{aid}/publish")
        self.assertEqual(pub.status, 200, pub)
        # antes da vigência: só PREVIEW, nada gravado
        pre = self.funder.get(f"/v1/signed-agreements/{aid}/allocation").json
        self.assertIsNone(pre["recorded"])
        self.assertEqual(pre["preview"]["platform_fee_cents"], 350_000, "3,5% de R$ 100.000,00 são R$ 3.500,00")
        self.assertEqual(self._assinar(aid, self.osc, self.funder), "active")

        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        al = d["allocation"]
        self.assertIsNotNone(al, "acordo vigente tem de ter a matriz GRAVADA")
        self.assertEqual((al["gross_cents"], al["project_cents"], al["platform_fee_cents"]), (10_000_000, 10_000_000, 350_000))
        self.assertEqual(al["fee_mode"], "additional", "modo adicional: o projeto recebe os R$ 100.000 inteiros")
        self.assertEqual(al["fee_bps"], 350)
        self.assertEqual(al["fee_rule_key"], "contract.platform_service_fee")
        self.assertFalse(al["fee_chargeable"], "a regra comercial nasce DESLIGADA: sem parecer, a taxa fica registrada e não é cobrada")
        self.assertIn("parecer", al["fee_reason"])
        self.assertIsNone(al["platform_charge_id"], "sem regra ativa, nenhuma cobrança é aberta")
        self.assertEqual(al["pricing_version"], "2027.01")
        self.assertEqual(len(al["allocation_hash"]), 64)
        linhas = {ln["kind"]: ln for ln in al["lines"]}
        self.assertEqual(linhas["project"]["cents"], 10_000_000)
        self.assertEqual(linhas["platform_fee"]["cents"], 350_000)
        self.assertIn("nunca descontada em trânsito", linhas["platform_fee"]["paid_by"])
        # nada na plataforma "segura" dinheiro: não existe payout, carteira ou saldo
        with db_system() as c:
            for tabela in ("payouts", "wallets", "wallet_balances", "escrow_accounts"):
                self.assertIsNone(c.scalar("SELECT to_regclass($1)", f"public.{tabela}"), f"{tabela} não pode existir (ADR-284)")
        # livro do projeto: ativação e matriz, encadeados
        livro = self.osc.get(f"/v1/projects/{self.project}/ledger").json
        tipos = [e["entry_type"] for e in livro["entries"]]
        self.assertIn("agreement_activated", tipos)
        self.assertIn("allocation_computed", tipos)
        self.assertTrue(livro["verification"]["valid"], livro["verification"])
        alloc_entry = next(e for e in livro["entries"] if e["entry_type"] == "allocation_computed")
        self.assertEqual(alloc_entry["payload"]["allocation_hash"], al["allocation_hash"])
        # o retrato é imutável
        with db_system() as c:
            with self.assertRaises(Exception):
                c.run("SET LOCAL ROLE impacto_app; UPDATE agreement_allocations SET platform_fee_cents = 0 WHERE id = $1", al["id"])

    def test_deducted_mode_sums_to_gross_and_gmv_is_not_revenue(self):
        aid = self._acordo(fee_mode="deducted")
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        self.assertEqual(self._assinar(aid, self.osc, self.funder), "active")
        al = self.osc.get(f"/v1/signed-agreements/{aid}/allocation").json["recorded"]
        self.assertEqual((al["gross_cents"], al["project_cents"], al["platform_fee_cents"]), (10_000_000, 9_650_000, 350_000))
        self.assertEqual(al["project_cents"] + al["platform_fee_cents"] + al["third_party_cents"], al["gross_cents"])
        # GMV ≠ receita: o valor contratado NÃO entra como receita reconhecida da plataforma
        from impacto.economics import metrics as M
        with db_system() as c:
            rec = M.revenue_recognized(c, period=dt.date.today())
        self.assertNotIn("10000000", str(rec).replace(" ", ""), "o valor contratado não é receita da plataforma")

    def test_with_the_rule_active_the_fee_becomes_a_platform_charge_to_the_funder(self):
        """Regra ativa (carta legal verde em ambiente de TESTE): a taxa vira cobrança própria da plataforma ao
        FINANCIADOR — não desconto no projeto. Ao final a regra volta a desligada."""
        from tests.support import owner_conn
        c = owner_conn()
        # Cartas legais são append-only: a única forma de "ficar verde" é registrar uma carta nova e completa.
        original = c.one("SELECT legal_card_id::text AS legal_card_id, legal_status FROM monetization_rules WHERE key = 'contract.platform_service_fee'")
        card = c.scalar(
            "INSERT INTO monetization_legal_cards(rule_key, payer, beneficiary, billing_event, revenue_nature, contractual_relation,"
            " legal_basis, source_name, source_url, verified_on, certainty, needs_lawyer, needs_accountant, status, note)"
            " VALUES ('contract.platform_service_fee', 'Financiador (parte do acordo)', 'Plataforma Impacto',"
            " 'ativação do acordo assinado com taxa de serviço contratada', 'prestação de serviço de software/orquestração',"
            " 'cláusula de taxa de serviço no acordo assinado pelas partes',"
            " 'Base de TESTE registrada exclusivamente para exercitar o portão de ativação; não é parecer.',"
            " 'Registro interno de teste', 'https://exemplo.test/base', current_date, 'high', false, false, 'green',"
            " 'carta de teste — ambiente de teste') RETURNING id::text")
        c.run("UPDATE monetization_rules SET legal_status = 'validated', legal_card_id = $1, active = true"
              " WHERE key = 'contract.platform_service_fee'", card)
        try:
            aid = self._acordo()
            self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
            self.assertEqual(self._assinar(aid, self.osc, self.funder), "active")
            al = self.osc.get(f"/v1/signed-agreements/{aid}/allocation").json["recorded"]
            self.assertTrue(al["fee_chargeable"])
            self.assertIsNotNone(al["platform_charge_id"])
            cob = self.funder.get("/v1/payments/charges").json
            minha = next(x for x in cob["items"] if x["id"] == al["platform_charge_id"])
            self.assertEqual(minha["amount_cents"], 350_000)
            self.assertEqual(minha["state"], "created", "cobrança ABERTA: nada foi cobrado, muito menos confirmado")
            self.assertTrue(minha["is_simulated"], "sem provedor real a cobrança é simulada e diz isso")
            # a OSC NÃO recebe cobrança nenhuma por este acordo
            da_osc = self.osc.get("/v1/payments/charges")
            if da_osc.status == 200:
                self.assertFalse(any(x["id"] == al["platform_charge_id"] for x in da_osc.json["items"]))
        finally:
            c.run("UPDATE monetization_rules SET active = false, legal_status = $1, legal_card_id = $2::uuid"
                  " WHERE key = 'contract.platform_service_fee'", original["legal_status"], original["legal_card_id"])
            c.close()
            # A carta verde é só de TESTE: cartas são append-only para a aplicação e para o dono do banco, então
            # removê-la exige o superusuário com os gatilhos suspensos — exatamente o nível de acesso que uma
            # adulteração real exigiria. Sem isso, a auditoria "nenhuma carta é verde" passaria a depender da ordem.
            subprocess.run(["psql", re.sub(r"/[^/]*$", f"/{DB_NAME}", ADMIN_URL), "-q", "-v", "ON_ERROR_STOP=1", "-v", f"card={card}"],
                           input="SET session_replication_role = replica;\nDELETE FROM monetization_legal_cards WHERE id = :'card'::uuid;\n",
                           check=True, capture_output=True, text=True)

    # ---------------------------------------------------------------- 2. obrigações e aceite
    def test_obligations_are_derived_from_the_contract_and_four_eyes_hold(self):
        aid = self._acordo(review_days=5, calendar="business")
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        self.assertEqual(self._assinar(aid, self.osc, self.funder), "active")
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        kinds = sorted(o["kind"] for o in d["obligations"])
        self.assertEqual(kinds, ["accept", "accept", "deliver", "deliver", "pay", "pay"], "2 marcos → entregar, aceitar e pagar cada um")
        entregar = next(o for o in d["obligations"] if o["kind"] == "deliver")
        self.assertEqual(entregar["obligor_org_id"], self.osc.org_id)
        pagar = next(o for o in d["obligations"] if o["kind"] == "pay")
        self.assertEqual((pagar["obligor_org_id"], pagar["amount_cents"]), (self.funder.org_id, 5_000_000))
        self.assertIsNone(pagar["due_on"], "pagar só tem prazo depois do aceite")
        # pendências de cada lado
        self.assertTrue(any(o["kind"] == "deliver" for o in self.osc.get("/v1/agreements/pending").json["items"]))
        self.assertTrue(any(o["kind"] == "accept" for o in self.funder.get("/v1/agreements/pending").json["items"]))
        m1 = d["milestones"][0]["id"]
        # a OSC entrega
        r = self.osc.patch(f"/v1/signed-agreements/{aid}/milestones/{m1}", {"status": "delivered", "note": "Instrumentos comprados; nota fiscal anexada."})
        self.assertEqual(r.status, 200, r)
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        ms = d["milestones"][0]
        self.assertEqual(ms["status"], "delivered")
        # prazo de aceite: 5 dias ÚTEIS a partir de hoje (política do acordo, não "7 dias")
        from impacto.trust.contract_rules import business_days
        self.assertEqual(ms["acceptance_due_on"], business_days(dt.date.today(), 5).isoformat())
        # quem entregou NÃO aceita a própria entrega
        r = self.osc.patch(f"/v1/signed-agreements/{aid}/milestones/{m1}", {"status": "accepted"})
        self.assertIn(r.status, (403, 422), r)
        # organização estranha ao acordo não aceita
        r = self.outra.patch(f"/v1/signed-agreements/{aid}/milestones/{m1}", {"status": "accepted"})
        self.assertIn(r.status, (403, 404), r)
        # o financiador aceita
        r = self.funder.patch(f"/v1/signed-agreements/{aid}/milestones/{m1}", {"status": "accepted", "note": "Conferido com a nota fiscal."})
        self.assertEqual(r.status, 200, r)
        d = self.funder.get(f"/v1/signed-agreements/{aid}").json
        self.assertEqual(d["milestones"][0]["status"], "accepted")
        self.assertEqual(d["milestones"][0]["accepted_by_org"], self.funder.org_id)
        pagar = next(o for o in d["obligations"] if o["kind"] == "pay" and o["milestone_id"] == m1)
        self.assertEqual(pagar["status"], "open")
        self.assertIsNotNone(pagar["due_on"], "aceito: a obrigação de pagar ganhou prazo")
        feitas = [o for o in d["obligations"] if o["milestone_id"] == m1 and o["status"] == "done"]
        self.assertEqual(sorted(o["kind"] for o in feitas), ["accept", "deliver"])
        # transição fora do grafo é recusada pelo banco
        r = self.funder.patch(f"/v1/signed-agreements/{aid}/milestones/{m1}", {"status": "planned"})
        self.assertEqual(r.status, 422, r)
        # recusa exige motivo
        m2 = d["milestones"][1]["id"]
        self.assertEqual(self.osc.patch(f"/v1/signed-agreements/{aid}/milestones/{m2}", {"status": "delivered"}).status, 200)
        self.assertEqual(self.funder.patch(f"/v1/signed-agreements/{aid}/milestones/{m2}", {"status": "rejected"}).status, 422)
        self.assertEqual(self.funder.patch(f"/v1/signed-agreements/{aid}/milestones/{m2}",
                                           {"status": "rejected", "note": "Faltam as listas de presença."}).status, 200)

    # ---------------------------------------------------------------- 3. versão
    def test_changing_an_approved_contract_creates_a_new_version_and_invalidates_the_old_approval(self):
        aid = self._acordo()
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        self.assertEqual(self._assinar(aid, self.osc, self.funder), "active")
        # termos publicados são imutáveis
        self.assertEqual(self.osc.patch(f"/v1/signed-agreements/{aid}", {"value_cents": 1}).status, 409)
        doc2 = upload(self.osc, name="acordo-v2.txt", body=b"Acordo de financiamento - versao 2 - valor revisto", doc_type="contrato")
        r = self.osc.post(f"/v1/signed-agreements/{aid}/new-version", {"document_id": doc2, "reason": "Valor revisto após corte no orçamento.",
                                                                        "value_cents": 8_000_000})
        self.assertEqual(r.status, 201, r)
        novo = r.json["id"]
        self.assertEqual(r.json["version"], 2)
        velho = self.osc.get(f"/v1/signed-agreements/{aid}").json
        self.assertEqual(velho["status"], "superseded", "OLD APPROVAL INVALIDATED")
        self.assertEqual(velho["terms"]["superseded_by_id"], novo)
        self.assertTrue(all(o["status"] == "waived" for o in velho["obligations"]), "obrigações da versão antiga caem")
        nv = self.osc.get(f"/v1/signed-agreements/{novo}").json
        self.assertEqual((nv["status"], nv["version"], nv["value_cents"]), ("draft", 2, 8_000_000))
        self.assertEqual(nv["pending_signatures"], 2, "todo mundo assina de novo")
        self.assertEqual(nv["allocation"], None)
        self.assertEqual(nv["allocation_preview"]["platform_fee_cents"], 280_000, "3,5% do valor NOVO")
        self.assertEqual(len(nv["milestones"]), 2, "marcos copiados")
        # versão substituída não volta
        with db_system() as c:
            with self.assertRaises(Exception):
                c.run("SET LOCAL ROLE impacto_app; UPDATE signed_agreements SET status = 'active' WHERE id = $1", aid)
        # histórico de versões registra a v1 publicada; a v2 entra quando for publicada
        self.assertEqual([v["version"] for v in velho["versions"]], [1])
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{novo}/publish").status, 200)
        self.assertEqual([v["version"] for v in self.osc.get(f"/v1/signed-agreements/{novo}").json["versions"]], [1, 2])

    # ---------------------------------------------------------------- 4. integridade
    def test_duplicate_activation_has_no_duplicate_effect_and_other_tenants_see_nothing(self):
        aid = self._acordo()
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        self.assertEqual(self._assinar(aid, self.osc, self.funder), "active")
        from impacto.trust import contract_rules
        with db_system() as c:
            out = contract_rules.activate(c, agreement_id=aid, actor_user_id=None)
            self.assertTrue(out["already"], "ativar de novo não cria nada")
            self.assertEqual(c.scalar("SELECT count(*) FROM agreement_allocations WHERE agreement_id = $1", aid), 1)
            self.assertEqual(c.scalar("SELECT count(*) FROM agreement_obligations WHERE agreement_id = $1", aid), 6)
        self.assertEqual(self.outra.get(f"/v1/signed-agreements/{aid}/allocation").status, 404)
        self.assertEqual(self.outra.get(f"/v1/signed-agreements/{aid}").status, 404)
        self.assertEqual(self.outra.get("/v1/agreements/pending").json["items"], [])

    def test_without_a_contracted_fee_there_is_no_fee_line_at_all(self):
        """Acordo de SERVIÇO (não de financiamento): a taxa é cláusula livre entre as partes; sem cláusula, não há linha.
        No acordo de financiamento ela vem do catálogo (v0.27.0) — ver test_v0270_economy."""
        doc = upload(self.osc, name="acordo-servico.txt", body=b"Acordo de servico sem taxa", doc_type="contrato")
        r = self.osc.post("/v1/signed-agreements", {"kind": "service", "title": "Prestação de serviço", "document_id": doc,
                                                    "project_id": self.project, "value_cents": 10_000_000})
        self.assertEqual(r.status, 201, r)
        aid = r.json["id"]
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/parties", {"org_id": self.funder.org_id, "role": "funder"}).status, 201)
        m = self.osc.post(f"/v1/signed-agreements/{aid}/milestones", {"title": "Entrega", "due_on": _d(30), "seq": 1, "amount_cents": 10_000_000})
        self.assertEqual(m.status, 201, m)
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        self.assertEqual(self._assinar(aid, self.osc, self.funder), "active")
        al = self.osc.get(f"/v1/signed-agreements/{aid}/allocation").json["recorded"]
        self.assertEqual(al["platform_fee_cents"], 0)
        self.assertEqual([ln["kind"] for ln in al["lines"]], ["project"])
        self.assertIn("não prevê", al["fee_reason"])


class TheFeeRuleIsBornDisabledTests(unittest.TestCase):
    def test_the_rule_exists_is_inactive_and_is_not_a_success_fee(self):
        server()
        with db_system() as c:
            r = c.one("SELECT active, legal_status, revenue_engine, pricing_mode, percentage FROM monetization_rules"
                      " WHERE key = 'contract.platform_service_fee'")
            card = c.one("SELECT lc.status, lc.needs_lawyer FROM monetization_rules r JOIN monetization_legal_cards lc ON lc.id = r.legal_card_id"
                         " WHERE r.key = 'contract.platform_service_fee'")
        self.assertFalse(r["active"])
        self.assertEqual(r["legal_status"], "review_required")
        self.assertNotIn(r["revenue_engine"], ("success_fee", "marketplace_take_rate"), "não é taxa de êxito nem take rate (ADR-022)")
        self.assertIsNone(r["percentage"], "o percentual vem do CONTRATO, não da regra")
        self.assertEqual(card["status"], "yellow")
        self.assertTrue(card["needs_lawyer"])
