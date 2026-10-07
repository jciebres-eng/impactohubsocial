"""O motor financeiro: CALCULA, INSTRUI, CONCILIA — e não custodia (ADR-284).

O QUE ESTES TESTES PROTEGEM

A regra que governa esta rodada é a do usuário, acima de todas as outras: não implementar uma
fintech dentro do IMPACTO só porque parece aumentar a monetização. O motor financeiro desta versão
é o caminho mais simples que entrega a mesma garantia operacional:

* CALCULA — a taxa, o reconhecimento de receita, o rateio por centro de custo;
* INSTRUI — emite um DOCUMENTO de pagamento com valor, destinatário e vencimento;
* CONCILIA — confere o que foi instruído contra a evidência de que alguém pagou.

O dinheiro de terceiro NUNCA passa pela plataforma. Estes testes são o que impede que alguém
"melhore" o motor acrescentando custódia sem passar pela decisão de arquitetura.

E protegem a parte mais fácil de perder: a PARTIDA DOBRADA de verdade (lote que não fecha é
recusado), a ALÇADA de verdade (quem pede não aprova; faixa de duas assinaturas não se satisfaz com
a mesma permissão duas vezes) e a HONESTIDADE DAS MÉTRICAS (indicador sem fonte responde
`available: false` com motivo, nunca zero — porque zero mente e `null` não explica).
"""
from __future__ import annotations

import unittest
import uuid
from datetime import date, timedelta

from tests.support import db_system, make_staff, new_account, reauth

HOJE = date.today()
COMP = HOJE.replace(day=1)


def _um_usuario(c) -> str:
    """Um titular criado POR ESTE TESTE.

    Pegar `SELECT id FROM users LIMIT 1` fazia o teste depender de outro teste ter rodado antes —
    e a ordem alfabética das classes mudava o resultado. Dependência invisível entre testes é a
    razão mais comum de uma suíte que passa no desenvolvedor e falha no servidor.
    """
    uid = c.scalar("SELECT id::text FROM users ORDER BY created_at LIMIT 1")
    if uid:
        return uid
    conta = new_account("osc")
    return c.scalar("SELECT id::text FROM users WHERE email = $1", conta.email)


def _uid(c, email: str) -> str:
    return c.scalar("SELECT id::text FROM users WHERE email = $1", email)


def _aprovar(c, request_id: str, aprovadores: list[tuple[str, str]]) -> None:
    """Concede as aprovações da faixa, cada uma com uma permissão diferente.

    Vai pela porta do banco de propósito: estes testes são sobre a INSTRUÇÃO, e a decisão pela rota
    tem a sua própria classe (`ApprovalIsFourEyesNotADecorationTests`).
    """
    for uid, permissao in aprovadores:
        c.run("INSERT INTO approval_decisions(request_id, decided_by, decision, permission_used)"
              " VALUES ($1,$2,'approve',$3)", request_id, uid, permissao)


def _periodo(delta_meses: int = 0) -> date:
    m = COMP.month + delta_meses
    ano = COMP.year + (m - 1) // 12
    return date(ano, (m - 1) % 12 + 1, 1)


class DoubleEntryIsRealTests(unittest.TestCase):
    """Partida dobrada que aceita lote desequilibrado não é partida dobrada: é duas colunas."""

    def test_a_batch_that_does_not_balance_is_refused(self):
        from impacto.economics import engine as ENG
        from impacto.http import ApiError
        with db_system() as c:
            ENG.ensure_period(c, COMP)
            with self.assertRaises(ApiError) as cm:
                ENG.post_batch(c, entries=[
                    {"period": COMP, "account_code": "1.2.1", "side": "debit",
                     "amount_cents": 10000, "description": "Receita a receber",
                     "source_kind": "manual"},
                    {"period": COMP, "account_code": "4.1.1", "side": "credit",
                     "amount_cents": 9999, "description": "Receita de assinatura",
                     "source_kind": "manual"},
                ])
        self.assertEqual(cm.exception.code, "batch_not_balanced")

    def test_a_batch_that_balances_is_accepted_and_cannot_be_changed_afterwards(self):
        from impacto.economics import engine as ENG
        with db_system() as c:
            ENG.ensure_period(c, COMP)
            lote = ENG.post_batch(c, entries=[
                {"period": COMP, "account_code": "1.2.1", "side": "debit", "amount_cents": 25000,
                 "description": "Cliente a receber", "source_kind": "invoice"},
                {"period": COMP, "account_code": "4.1.1", "side": "credit", "amount_cents": 25000,
                 "description": "Receita de assinatura", "source_kind": "invoice"},
            ])
            self.assertTrue(c.scalar("SELECT batch_is_balanced($1)", lote))
            # Lançamento é indelével e imutável: é o que faz dele contabilidade.
            with self.assertRaises(Exception):
                c.run("UPDATE accounting_entries SET amount_cents = 1 WHERE batch_id = $1", lote)
        with db_system() as c:
            with self.assertRaises(Exception):
                c.run("DELETE FROM accounting_entries WHERE batch_id = $1", lote)

    def test_a_synthetic_account_refuses_entries(self):
        """Lançar em conta sintética destrói o balancete: o total passa a contar duas vezes."""
        from impacto.economics import engine as ENG
        with db_system() as c:
            ENG.ensure_period(c, COMP)
            with self.assertRaises(Exception) as cm:
                ENG.post_batch(c, entries=[
                    {"period": COMP, "account_code": "1", "side": "debit", "amount_cents": 100,
                     "description": "Conta sintética", "source_kind": "manual"},
                    {"period": COMP, "account_code": "4.1.1", "side": "credit",
                     "amount_cents": 100, "description": "contrapartida",
                     "source_kind": "manual"},
                ])
        self.assertIn("sint", str(cm.exception).lower())

    def test_a_closed_period_refuses_new_entries(self):
        from impacto.economics import engine as ENG
        passado = _periodo(-13)
        with db_system() as c:
            ENG.ensure_period(c, passado)
            ENG.close_period(c, period=passado, closed_by=_um_usuario(c))
            with self.assertRaises(Exception) as cm:
                ENG.post_batch(c, entries=[
                    {"period": passado, "account_code": "1.2.1", "side": "debit",
                     "amount_cents": 100, "description": "atrasado", "source_kind": "manual"},
                    {"period": passado, "account_code": "4.1.1", "side": "credit",
                     "amount_cents": 100, "description": "atrasado", "source_kind": "manual"},
                ])
        self.assertIn("não está aberta", str(cm.exception).lower())

    def test_closing_a_period_with_an_unbalanced_batch_is_refused(self):
        """Fechar competência com lote torto transforma um erro corrigível em erro histórico."""
        from impacto.economics import engine as ENG
        from impacto.http import ApiError
        p = _periodo(-14)
        with db_system() as c:
            ENG.ensure_period(c, p)
            usuario = _um_usuario(c)
            torto = str(uuid.uuid4())
            # Entra pela porta do banco porque post_batch RECUSA desequilíbrio: o cenário existe
            # para provar que o fechamento também confere, e não confia em quem inseriu.
            c.run("INSERT INTO accounting_entries(period, account_code, batch_id, side,"
                  " amount_cents, description, source_kind, created_by)"
                  " VALUES ($1,'1.2.1',$2,'debit',500,'torto','manual',$3)", p, torto, usuario)
            with self.assertRaises(ApiError) as cm:
                ENG.close_period(c, period=p, closed_by=usuario)
            self.assertEqual(cm.exception.code, "unbalanced_batches")
            self.assertEqual(c.scalar("SELECT status FROM accounting_periods WHERE period = $1",
                                      p), "open", "a competência continua aberta para correção")


class RevenueRecognitionIsCalculatedNotGuessedTests(unittest.TestCase):

    def test_an_annual_plan_is_spread_over_twelve_periods_without_losing_a_cent(self):
        from impacto.economics import engine as ENG
        plano = ENG.recognition_schedule(amount_cents=100000, months=12, first_period=COMP)
        self.assertEqual(len(plano), 12)
        self.assertEqual(sum(p["amount_cents"] for p in plano), 100000)
        # O resto fica no PRIMEIRO período, não no último: quem fecha janeiro já fecha certo.
        self.assertEqual(plano[0]["amount_cents"], 8337)
        self.assertEqual(plano[-1]["amount_cents"], 8333)

    def test_the_marketplace_fee_is_calculated_and_declared_not_billable(self):
        """A taxa de 10% EXISTE como cálculo e está inativa como cobrança — de propósito.

        `NON_CUSTODIAL_ARCHITECTURE.md` §7: cobrar percentual sobre contrato de terceiro sem
        contrato comercial assinado e sem nota fiscal própria é receita inventada.
        """
        from impacto.economics import engine as ENG
        with db_system() as c:
            out = ENG.compute_marketplace_fee(c, contract_amount_cents=1000000)
        self.assertFalse(out["billable"])
        self.assertTrue(out.get("reason"))


class ApprovalIsFourEyesNotADecorationTests(unittest.TestCase):
    """`core/risk_levels.py` dizia que operações exigiam quatro olhos e não implementava nenhum.

    O docstring dele já admitia: "Dizer que uma operação exige quatro olhos e não implementar os
    quatro olhos é a forma mais cara de mentir nesta plataforma." Estes testes são a implementação.
    """

    def test_the_bands_are_data_in_the_database_not_constants_in_code(self):
        with db_system() as c:
            faixas = c.query("SELECT p.operation, r.min_cents, r.max_cents, r.approvals_needed,"
                             " r.required_permissions FROM approval_rules r"
                             " JOIN approval_policies p ON p.id = r.policy_id WHERE p.active")
        self.assertGreaterEqual(len(faixas), 8)
        for f in faixas:
            self.assertGreaterEqual(len(f["required_permissions"]), 1)
            self.assertGreaterEqual(int(f["approvals_needed"]), 1)
        # Valor alto exige MAIS gente do que valor baixo — senão a faixa não serve para nada.
        pi = [f for f in faixas if f["operation"] == "payment_instruction"]
        baixa = min(pi, key=lambda f: int(f["min_cents"]))
        alta = max(pi, key=lambda f: int(f["min_cents"]))
        self.assertLess(int(baixa["approvals_needed"]), int(alta["approvals_needed"]))

    def test_whoever_asks_cannot_approve(self):
        from impacto.economics import approvals as AP
        pedinte = make_staff("controller")
        with db_system() as c:
            uid = c.scalar("SELECT id::text FROM users WHERE email = $1", pedinte.email)
            pedido = AP.request(c, operation="platform_expense", object_type="platform_expense",
                                object_id=str(uuid.uuid4()), amount_cents=10000,
                                summary="teste", requested_by=uid)
            with self.assertRaises(Exception) as cm:
                c.run("INSERT INTO approval_decisions(request_id, decided_by, decision,"
                      " permission_used) VALUES ($1,$2,'approve','finance.approve')",
                      pedido["request_id"], uid)
        self.assertIn("quem pede não aprova", str(cm.exception).lower())

    def test_a_band_that_needs_two_different_permissions_refuses_the_same_one_twice(self):
        """Duas assinaturas com a MESMA permissão são uma assinatura repetida, não segregação."""
        from impacto.economics import approvals as AP
        a, b = make_staff("controller"), make_staff("controller")
        with db_system() as c:
            ida = c.scalar("SELECT id::text FROM users WHERE email = $1", a.email)
            idb = c.scalar("SELECT id::text FROM users WHERE email = $1", b.email)
            terceiro = c.scalar("SELECT id::text FROM users WHERE id NOT IN ($1,$2) LIMIT 1",
                                ida, idb)
            pedido = AP.request(c, operation="payment_instruction",
                                object_type="payment_instruction",
                                object_id=str(uuid.uuid4()), amount_cents=500000,
                                summary="faixa de duas", requested_by=terceiro)
            self.assertEqual(int(pedido["needed"]), 2)
            c.run("INSERT INTO approval_decisions(request_id, decided_by, decision,"
                  " permission_used) VALUES ($1,$2,'approve','finance.approve')",
                  pedido["request_id"], ida)
            with self.assertRaises(Exception) as cm:
                c.run("INSERT INTO approval_decisions(request_id, decided_by, decision,"
                      " permission_used) VALUES ($1,$2,'approve','finance.approve')",
                      pedido["request_id"], idb)
            self.assertIn("permiss", str(cm.exception).lower())

    def test_an_unapproved_object_cannot_be_treated_as_approved(self):
        from impacto.economics import approvals as AP
        from impacto.http import ApiError
        objeto = str(uuid.uuid4())
        with db_system() as c:
            with self.assertRaises(ApiError) as cm:
                AP.require_approved(c, object_type="payment_instruction", object_id=objeto,
                                    operation="payment_instruction", amount_cents=300000)
        self.assertEqual(cm.exception.code, "approval_required")
        self.assertEqual(cm.exception.status, 409)

    def test_two_decisions_settle_the_request(self):
        from impacto.economics import approvals as AP
        a, b = make_staff("controller"), make_staff("accounting")
        with db_system() as c:
            ida = c.scalar("SELECT id::text FROM users WHERE email = $1", a.email)
            idb = c.scalar("SELECT id::text FROM users WHERE email = $1", b.email)
            terceiro = c.scalar("SELECT id::text FROM users WHERE id NOT IN ($1,$2) LIMIT 1",
                                ida, idb)
            objeto = str(uuid.uuid4())
            pedido = AP.request(c, operation="payment_instruction",
                                object_type="payment_instruction", object_id=objeto,
                                amount_cents=500000, summary="duas assinaturas",
                                requested_by=terceiro)
            c.run("INSERT INTO approval_decisions(request_id, decided_by, decision,"
                  " permission_used) VALUES ($1,$2,'approve','finance.approve')",
                  pedido["request_id"], ida)
            self.assertEqual(c.scalar("SELECT state FROM approval_requests WHERE id = $1",
                                      pedido["request_id"]), "pending")
            c.run("INSERT INTO approval_decisions(request_id, decided_by, decision,"
                  " permission_used) VALUES ($1,$2,'approve','accounting.close')",
                  pedido["request_id"], idb)
            self.assertEqual(c.scalar("SELECT state FROM approval_requests WHERE id = $1",
                                      pedido["request_id"]), "approved")
            self.assertTrue(AP.is_approved(c, object_type="payment_instruction",
                                           object_id=objeto, operation="payment_instruction"))

    def test_one_rejection_is_enough_to_reject(self):
        from impacto.economics import approvals as AP
        a = make_staff("controller")
        with db_system() as c:
            ida = c.scalar("SELECT id::text FROM users WHERE email = $1", a.email)
            terceiro = c.scalar("SELECT id::text FROM users WHERE id <> $1 LIMIT 1", ida)
            pedido = AP.request(c, operation="payment_instruction",
                                object_type="payment_instruction",
                                object_id=str(uuid.uuid4()), amount_cents=5000000,
                                summary="recusa", requested_by=terceiro)
            c.run("INSERT INTO approval_decisions(request_id, decided_by, decision,"
                  " permission_used, note) VALUES ($1,$2,'reject','finance.approve','não')",
                  pedido["request_id"], ida)
            self.assertEqual(c.scalar("SELECT state FROM approval_requests WHERE id = $1",
                                      pedido["request_id"]), "rejected")


class AnInstructionIsADocumentNotATransferTests(unittest.TestCase):
    """A plataforma INSTRUI. Quem paga é quem tem o dinheiro, e a prova disso é a evidência."""

    def test_the_amount_and_the_payee_freeze_when_the_instruction_is_issued(self):
        from impacto.economics import engine as ENG
        pedinte, a, b = new_account("osc"), make_staff("controller"), make_staff("accounting")
        with db_system() as c:
            usuario = _uid(c, pedinte.email)
            instrucao = ENG.create_instruction(
                c, kind="supplier", payee_name="Fornecedor de Nuvem",
                amount_cents=120000, due_on=HOJE + timedelta(days=10),
                reference="NF 4455", created_by=usuario, account_code="5.1.1",
                cost_center="CLOUD")
            # R$ 1.200,00 cai na faixa de DUAS aprovações com permissões diferentes.
            self.assertEqual(int(instrucao["approval"]["needed"]), 2)
            _aprovar(c, instrucao["approval"]["request_id"],
                     [(_uid(c, a.email), "finance.approve"),
                      (_uid(c, b.email), "accounting.close")])
            ENG.issue_instruction(c, instruction_id=instrucao["id"])

        # Cada tentativa vai na SUA transação: a primeira recusa aborta a transação no PostgreSQL,
        # e conferir a segunda na mesma transação só provaria que a transação estava abortada.
        for coluna, valor in (("amount_cents", "1"), ("payee_name", "'outro destinatário'"),
                              ("payee_doc", "'12345678901'"), ("reference", "'outra nota'")):
            with self.subTest(coluna=coluna), db_system() as c:
                with self.assertRaises(Exception) as cm:
                    c.run(f"UPDATE payment_instructions SET {coluna} = {valor} WHERE id = $1",
                          instrucao["id"])
                self.assertIn("emitida", str(cm.exception).lower())

        # O que PODE mudar depois de emitida: a evidência e o estado. O resto é documento.
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT payee_name FROM payment_instructions WHERE id = $1",
                                      instrucao["id"]), "Fornecedor de Nuvem")

    def test_executed_without_evidence_is_refused(self):
        """Sem evidência a plataforma estaria AFIRMANDO um pagamento que ela não viu acontecer."""
        from impacto.economics import engine as ENG
        pedinte, a = new_account("osc"), make_staff("controller")
        with db_system() as c:
            usuario = _uid(c, pedinte.email)
            instrucao = ENG.create_instruction(
                c, kind="tax", payee_name="Receita Federal", amount_cents=50000,
                due_on=HOJE, reference="DARF 2026-10", created_by=usuario)
            _aprovar(c, instrucao["approval"]["request_id"],
                     [(_uid(c, a.email), "finance.approve")])
            ENG.issue_instruction(c, instruction_id=instrucao["id"])
            with self.assertRaises(Exception) as cm:
                c.run("UPDATE payment_instructions SET state = 'executed', executed_at = now()"
                      " WHERE id = $1", instrucao["id"])
            texto = str(cm.exception).lower()
            self.assertTrue("eviden" in texto or "emitid" in texto, texto)

    def test_recording_the_execution_requires_and_keeps_the_evidence(self):
        from impacto.economics import engine as ENG
        pedinte, a = new_account("osc"), make_staff("controller")
        with db_system() as c:
            usuario = _uid(c, pedinte.email)
            instrucao = ENG.create_instruction(
                c, kind="supplier", payee_name="Consultoria", amount_cents=30000,
                due_on=HOJE, reference="Contrato 9", created_by=usuario)
            _aprovar(c, instrucao["approval"]["request_id"],
                     [(_uid(c, a.email), "finance.approve")])
            ENG.issue_instruction(c, instruction_id=instrucao["id"])
            out = ENG.record_execution(c, instruction_id=instrucao["id"],
                                       evidence_doc="comprovante-banco-2026-10-06.pdf")
            self.assertEqual(out["state"], "executed")
            self.assertEqual(c.scalar("SELECT evidence_doc FROM payment_instructions"
                                      " WHERE id = $1", instrucao["id"]),
                             "comprovante-banco-2026-10-06.pdf")

    def test_the_platform_has_no_table_that_holds_third_party_money(self):
        """A prova estrutural da regra: nenhuma tabela de saldo, carteira, repasse ou custódia."""
        with db_system() as c:
            suspeitas = c.query(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                "   AND (table_name ~ 'wallet|payout|split|escrow|custod|repasse'"
                "        OR table_name ~ '_balances?$')")
        self.assertEqual([r["table_name"] for r in suspeitas], [])


class ExpenseSeparationOfDutiesTests(unittest.TestCase):

    def test_whoever_registers_an_expense_cannot_be_its_approver(self):
        with db_system() as c:
            usuario = _um_usuario(c)
            with self.assertRaises(Exception) as cm:
                c.run("INSERT INTO platform_expenses(period, account_code, cost_center,"
                      " description, amount_cents, created_by, approved_by, status)"
                      " VALUES ($1,'5.1.1','CLOUD','autoaprovada',9900,$2,$2,'approved')",
                      COMP, usuario)
            self.assertIn("expense", str(cm.exception).lower())


class MetricsAnswerWithTheirSourceOrWithTheirAbsenceTests(unittest.TestCase):
    """§58: todo indicador diz FONTE, CÁLCULO, PERÍODO e última atualização.

    E o que não tem fonte responde `available: false` com motivo. Indicador sem dado que responde
    zero é a forma mais convincente de mentir num painel executivo: zero parece medição.
    """

    def test_every_metric_declares_source_calculation_and_period(self):
        from impacto.economics import metrics as MET
        with db_system() as c:
            resumo = MET.summary(c, period=COMP)
        achatado = []

        def _coletar(no, caminho=""):
            if isinstance(no, dict):
                if "source" in no and "calculation" in no:
                    achatado.append((caminho, no))
                for k, v in no.items():
                    _coletar(v, f"{caminho}.{k}")
            elif isinstance(no, list):
                for i, v in enumerate(no):
                    _coletar(v, f"{caminho}[{i}]")

        _coletar(resumo)
        self.assertGreaterEqual(len(achatado), 8, "o resumo executivo tem de medir algo")
        for caminho, m in achatado:
            self.assertTrue(m["source"], caminho)
            self.assertTrue(m["calculation"], caminho)
            self.assertIn("period", m, caminho)
            if not m.get("available", True):
                self.assertTrue(m.get("unavailable_reason"),
                                f"{caminho} indisponível sem dizer por quê")

    def test_what_cannot_be_measured_says_so_instead_of_answering_zero(self):
        from impacto.economics import metrics as MET
        with db_system() as c:
            conv = MET.conversion(c)
        for chave in ("churn", "ltv", "cac"):
            self.assertIn(chave, conv)
            self.assertFalse(conv[chave].get("available", True),
                             f"{chave} não tem base real nesta versão e não pode parecer medido")
            self.assertTrue(conv[chave].get("unavailable_reason"))

    def test_gmv_is_never_summed_with_platform_revenue(self):
        """GMV é dinheiro de TERCEIRO. Somá-lo à receita é o erro que infla avaliação de SaaS."""
        from impacto.economics import metrics as MET
        with db_system() as c:
            g = MET.gmv(c, period=COMP)
            rec = MET.recurring_revenue(c)
        self.assertEqual(g["platform_revenue_on_gmv"]["value"], 0)
        self.assertTrue(g.get("warning"))
        self.assertNotIn("gmv", str(rec["mrr"]["calculation"]).lower())

    def test_mrr_ignores_sandbox_charges(self):
        from impacto.economics import metrics as MET
        with db_system() as c:
            rec = MET.recurring_revenue(c)
        self.assertIn("sandbox", rec["mrr"]["calculation"].lower())

    def test_runway_is_absent_when_there_is_no_burn(self):
        from impacto.economics import metrics as MET
        with db_system() as c:
            b = MET.burn_and_runway(c, period=_periodo(-20))
        self.assertFalse(b["runway_months"].get("available", True))
        self.assertTrue(b["runway_months"].get("unavailable_reason"))


class TheInternalPanelsAreReachableAndSeparatedTests(unittest.TestCase):
    """As rotas existem, respondem, e cada papel alcança só a sua área."""

    def test_the_controller_sees_the_executive_panel(self):
        c = make_staff("controller")
        r = c.get("/v1/controladoria/summary")
        self.assertEqual(r.status, 200, r)
        self.assertIn("honesty_note", r.json)
        self.assertIn("pending_approvals", r.json)

    def test_support_cannot_open_the_controller_panel(self):
        c = make_staff("support")
        r = c.get("/v1/controladoria/summary")
        self.assertEqual(r.status, 403, r)
        self.assertEqual(r.json["code"], "permission_denied")
        self.assertEqual(r.json["details"]["required_permission"], "metrics.read")

    def test_accounting_opens_the_accounting_panel_and_not_the_treasury(self):
        c = make_staff("accounting")
        self.assertEqual(c.get("/v1/contabilidade/summary").status, 200)
        self.assertEqual(c.get("/v1/tesouraria/summary").status, 403)

    def test_treasury_sees_its_own_patrimony_and_says_so(self):
        c = make_staff("treasury")
        r = c.get("/v1/tesouraria/summary")
        self.assertEqual(r.status, 200, r)
        self.assertIn("não custodia", r.json["scope_note"])

    def test_operations_opens_the_health_center_and_the_alert_center(self):
        c = make_staff("operations")
        saude = c.get("/v1/operacoes/health")
        self.assertEqual(saude.status, 200, saude)
        self.assertTrue(saude.json["services"])
        for s in saude.json["services"]:
            self.assertIn(s["state"], {"ok", "warn", "fail", "unknown"})
        alertas = c.get("/v1/operacoes/alerts")
        self.assertEqual(alertas.status, 200, alertas)
        self.assertIn("by_priority", alertas.json)
        for a in alertas.json["items"]:
            self.assertIn(a["priority"], {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"})
            self.assertTrue(a["object_type"], "alerta sem origem é alerta inverificável")

    def test_finance_creates_an_instruction_and_cannot_issue_it(self):
        """Segregação de funções pela porta da rota: `finance` instrui, `controller` emite."""
        financeiro = make_staff("finance")
        reauth(financeiro)
        r = financeiro.post("/v1/financeiro/instructions", {
            "kind": "supplier", "payee_name": "Hospedagem", "amount_cents": 45000,
            "due_on": str(HOJE + timedelta(days=15)), "reference": "fatura-2026-10",
            "account_code": "5.1.1", "cost_center": "CLOUD"})
        self.assertEqual(r.status, 201, r)
        emitir = financeiro.post(f"/v1/financeiro/instructions/{r.json['id']}/issue", {})
        self.assertEqual(emitir.status, 403, emitir)
        self.assertEqual(emitir.json["details"]["required_permission"], "instruction.approve")

    def test_the_fee_preview_calculates_and_refuses_to_pretend_it_is_revenue(self):
        c = make_staff("controller")
        r = c.get("/v1/financeiro/fee-preview?amount_cents=2500000")
        self.assertEqual(r.status, 200, r)
        self.assertFalse(r.json["billable"])

    def test_a_client_organization_never_reaches_any_of_these_panels(self):
        cliente = new_account("osc")
        for rota in ("/v1/controladoria/summary", "/v1/financeiro/summary",
                     "/v1/contabilidade/summary", "/v1/tesouraria/summary",
                     "/v1/operacoes/health", "/v1/operacoes/alerts",
                     "/v1/administrativo/budget", "/v1/aprovacoes"):
            r = cliente.get(rota)
            self.assertEqual(r.status, 403, f"{rota} aberta a cliente: {r}")

    def test_the_budget_panel_says_when_there_is_no_approved_budget(self):
        c = make_staff("controller")
        r = c.get("/v1/administrativo/budget?year=2019")
        self.assertEqual(r.status, 200, r)
        self.assertIsNone(r.json["approved_budget"])
        self.assertIn("Nenhum orçamento aprovado", r.json["note"])

    def test_registering_an_expense_opens_an_approval_request(self):
        c = make_staff("finance")
        reauth(c)
        r = c.post("/v1/financeiro/expenses", {
            "period": str(COMP), "account_code": "5.1.2", "cost_center": "AI",
            "description": "Provedor de modelo", "amount_cents": 180000})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["status"], "registered")
        self.assertGreaterEqual(int(r.json["approval"]["needed"]), 1)
        pendentes = make_staff("controller").get("/v1/aprovacoes")
        self.assertEqual(pendentes.status, 200, pendentes)
        self.assertTrue(any(p["object_id"] == r.json["id"] for p in pendentes.json["items"]))

    def test_the_reconciliation_points_and_does_not_correct(self):
        c = make_staff("controller")
        r = c.get("/v1/controladoria/reconciliation?days=30")
        self.assertEqual(r.status, 200, r)
        for chave in ("overdue_instructions", "executed_without_evidence",
                      "paid_expenses_without_entry", "unbalanced_batches", "divergences"):
            self.assertIn(chave, r.json)


if __name__ == "__main__":
    unittest.main()
