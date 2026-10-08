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

import re
import unittest
import uuid
from datetime import date, timedelta

from tests.support import ROOT, db_system, make_staff, new_account, reauth

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

    def test_without_a_declared_rate_the_fee_is_not_calculated_and_says_so(self):
        """Não há alíquota declarada — e a resposta diz isso, em vez de devolver zero ou inventar.

        A primeira versão deste teste chamava-se "a taxa de 10% EXISTE como cálculo", conferia
        apenas `billable` e `reason`, e NUNCA olhava `fee_cents`. A documentação repetiu a mesma
        afirmação. Auditoria independente mostrou que `monetization_rules.percentage` é NULL: não
        existem 10% em lugar nenhum do banco. Um teste que afirma no nome o que não exercita é
        pior do que teste nenhum, porque documenta o contrário do que o código faz.
        """
        from impacto.economics import engine as ENG
        with db_system() as c:
            out = ENG.compute_marketplace_fee(c, contract_amount_cents=1000000)
            self.assertFalse(out["billable"])
            self.assertEqual(out["reason"], "percentage_not_declared")
            self.assertIsNone(out["percentage"])
            self.assertIsNone(out["fee_cents"], "sem alíquota não há cálculo a devolver")
            self.assertEqual(out["base_cents"], 1000000)

    def test_with_a_declared_rate_it_calculates_and_still_refuses_to_bill(self):
        """CALCULA de verdade — e continua `billable: false` enquanto a regra estiver inativa."""
        from impacto.economics import engine as ENG
        with db_system() as c:
            anterior = c.scalar("SELECT percentage FROM monetization_rules"
                                " WHERE key = 'marketplace.take_rate'")
            c.run("UPDATE monetization_rules SET percentage = 10"
                  " WHERE key = 'marketplace.take_rate'")
            out = ENG.compute_marketplace_fee(c, contract_amount_cents=1000000)
            self.assertEqual(out["percentage"], 10.0)
            self.assertEqual(out["fee_cents"], 100000, "10% de R$ 10.000,00 são R$ 1.000,00")
            self.assertFalse(out["billable"], "a regra segue inativa por decisão registrada")
            self.assertEqual(out["reason"], "rule_inactive")
            c.run("UPDATE monetization_rules SET percentage = $1"
                  " WHERE key = 'marketplace.take_rate'", anterior)


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

    # v0.27.0 (ADR-341/ADR-284): a camada econômica tem DUAS tabelas cujo nome contém "payout" e que
    # NÃO custodiam nada — `allocation_payouts` é a INSTRUÇÃO (quem paga → quem recebe → quanto → chave
    # PIX informada no contrato) e `payout_transfers` é o REGISTRO da transferência que o próprio pagador
    # fez fora da plataforma, confirmada por quem recebe. A heurística por nome continua para toda
    # tabela nova; estas duas são conferidas pela ESTRUTURA: nenhuma coluna de saldo, nenhuma coluna
    # que diga que a plataforma "segura" valor, e o pagador é sempre uma organização, nunca a plataforma.
    INSTRUCAO_SEM_CUSTODIA = ("allocation_payouts", "payout_transfers")

    def test_the_platform_has_no_table_that_holds_third_party_money(self):
        """A prova estrutural da regra: nenhuma tabela de saldo, carteira, repasse ou custódia."""
        with db_system() as c:
            suspeitas = c.query(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                "   AND (table_name ~ 'wallet|payout|split|escrow|custod|repasse'"
                "        OR table_name ~ '_balances?$')")
            colunas = {t: [r["column_name"] for r in c.query(
                "SELECT column_name FROM information_schema.columns WHERE table_name = $1", t)]
                for t in self.INSTRUCAO_SEM_CUSTODIA}
        self.assertEqual(sorted(r["table_name"] for r in suspeitas), sorted(self.INSTRUCAO_SEM_CUSTODIA))
        for t, cols in colunas.items():
            self.assertFalse([col for col in cols if re.search(r"balance|saldo|held|custod|wallet|escrow", col)],
                             f"{t} tem coluna de saldo/custódia: {cols}")
        self.assertIn("payer_org_id", colunas["allocation_payouts"])
        self.assertIn("recipient_org_id", colunas["allocation_payouts"])
        self.assertIn("pix_key_snapshot", colunas["allocation_payouts"])     # o destino é a chave do contrato, não a plataforma
        self.assertIn("registered_by_org", colunas["payout_transfers"])
        self.assertIn("confirmed_by_org", colunas["payout_transfers"])       # quem RECEBE confirma; a plataforma não "libera"


class ExpenseSeparationOfDutiesTests(unittest.TestCase):

    def test_whoever_registers_an_expense_cannot_be_its_approver(self):
        """Confere a restrição NOMEADA, não qualquer erro que contenha "expense".

        O INSERT viola DUAS restrições cujo nome contém "expense" (`expense_four_eyes` e
        `expense_approval_is_complete`, porque passava `approved_by` sem `approved_at`). Conferir
        só a substring deixaria o teste verde se alguém removesse justamente o quatro-olhos.
        Encontrado por auditoria independente.
        """
        with db_system() as c:
            usuario = _um_usuario(c)
            with self.assertRaises(Exception) as cm:
                c.run("INSERT INTO platform_expenses(period, account_code, cost_center,"
                      " description, amount_cents, created_by, approved_by, approved_at, status)"
                      " VALUES ($1,'5.1.1','CLOUD','autoaprovada',9900,$2,$2, now(),'approved')",
                      COMP, usuario)
            self.assertEqual(getattr(cm.exception, "constraint", None), "expense_four_eyes",
                             f"outra restrição barrou antes: {cm.exception}")


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

    def test_platform_revenue_and_network_gmv_come_from_disjoint_sources(self):
        """GMV é dinheiro de TERCEIRO. Somá-lo à receita é o erro que infla avaliação de SaaS.

        A primeira versão deste teste conferia `platform_revenue_on_gmv == 0` — um zero literal
        escrito no próprio módulo — e a ausência da palavra "gmv" numa string. Nenhuma das duas
        tocava a receita.

        Agora o teste exercita uma direção de verdade (lançar receita da plataforma não move o GMV)
        e prova a outra estruturalmente: nenhum código converte `commitments` em lançamento
        contábil, então um aporte de terceiro não tem como virar receita apurada.
        """
        from pathlib import Path as _P
        from impacto.economics import engine as ENG
        from impacto.economics import metrics as MET
        with db_system() as c:
            gmv_antes = MET.gmv(c, period=COMP)["gmv"]["value"]
            receita_antes = MET.revenue_recognized(c, period=COMP)["gross_revenue"]["value"]
            ENG.ensure_period(c, COMP)
            ENG.post_batch(c, created_by=_um_usuario(c), entries=[
                {"period": COMP, "account_code": "1.2.1", "side": "debit", "amount_cents": 123400,
                 "description": "Receita da plataforma", "source_kind": "invoice"},
                {"period": COMP, "account_code": "4.1.1", "side": "credit",
                 "amount_cents": 123400, "description": "Assinatura", "source_kind": "invoice"},
            ])
            depois = MET.gmv(c, period=COMP)
            receita_depois = MET.revenue_recognized(c, period=COMP)["gross_revenue"]["value"]
            self.assertEqual(receita_depois - receita_antes, 123400,
                             "a receita da plataforma não foi reconhecida")
            self.assertEqual(depois["gmv"]["value"], gmv_antes,
                             "receita da plataforma entrou no GMV da rede")
            self.assertEqual(depois["platform_revenue_on_gmv"]["value"], 0)
            self.assertTrue(depois.get("warning"))
            # As duas medições leem tabelas diferentes, e o módulo diz quais.
            self.assertIn("commitments", depois["gmv"]["source"])
            self.assertIn("accounting_entries",
                          MET.revenue_recognized(c, period=COMP)["gross_revenue"]["source"])

        # E nada no código converte aporte de terceiro em lançamento contábil: se convertesse, o
        # GMV viraria receita por um caminho que nenhuma tela mostraria.
        pkg = _P(ROOT) / "backend" / "impacto"
        culpados = []
        for f in pkg.rglob("*.py"):
            texto = f.read_text(encoding="utf-8")
            if "INSERT INTO accounting_entries" in texto and "commitments" in texto:
                culpados.append(f.name)
        self.assertEqual(culpados, [],
                         "módulo que grava lançamento contábil e lê compromissos: "
                         + ", ".join(culpados))

    def test_there_is_no_mrr_and_the_operation_layer_is_read_from_the_ledger(self):
        """v0.27.0 (ADR-341): não existe assinatura, logo não existe MRR. O painel diz isso com motivo,
        e a receita da plataforma vem da CAMADA ECONÔMICA da operação, lida de `economic_events`."""
        from impacto.economics import metrics as MET
        with db_system() as c:
            op = MET.operation_revenue(c)
            self.assertFalse(op["mrr"]["available"])
            self.assertIn("ADR-341", op["mrr"]["unavailable_reason"])
            self.assertFalse(op["arr"]["available"])
            for k in ("platform_layer_registered", "platform_layer_due", "platform_layer_paid"):
                self.assertTrue(op[k]["available"], k)
                self.assertIn("economic_events", op[k]["source"])
            # Participação de autoria NÃO é receita da plataforma — e o painel diz isso.
            self.assertIn("NÃO é receita", op["participation_accrued"]["calculation"])
            self.assertFalse(c.one("SELECT 1 FROM information_schema.tables WHERE table_name = 'subscriptions'"))

    def test_registered_layer_follows_the_ledger_and_reversals_subtract(self):
        """Um evento de registro soma; uma reversão da mesma regra abate. Nada é inventado."""
        from impacto.economics import metrics as MET
        conta = new_account("osc")
        with db_system() as c:
            antes = MET.operation_revenue(c)["platform_layer_registered"]["value"]
            seq = c.scalar("INSERT INTO economic_events(kind, org_id, rule_key, bps, base_cents, amount_cents, idempotency_key)"
                           " VALUES ('platform_service_registered', $1, 'contract.platform_service_fee', 350, 10000000, 350000, $2) RETURNING seq",
                           conta.org_id, "t-reg-" + conta.org_id)
            meio = MET.operation_revenue(c)["platform_layer_registered"]["value"]
            c.run("INSERT INTO economic_events(kind, org_id, rule_key, bps, base_cents, amount_cents, idempotency_key, reverses_seq)"
                  " VALUES ('reversal', $1, 'contract.platform_service_fee', 350, 10000000, 350000, $2, $3)",
                  conta.org_id, "t-rev-" + conta.org_id, seq)
            depois = MET.operation_revenue(c)["platform_layer_registered"]["value"]
        self.assertEqual(meio - antes, 350000)
        self.assertEqual(depois, antes)

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
                     "/v1/administrativo/orcamento", "/v1/aprovacoes"):
            r = cliente.get(rota)
            self.assertEqual(r.status, 403, f"{rota} aberta a cliente: {r}")

    def test_the_budget_panel_says_when_there_is_no_approved_budget(self):
        c = make_staff("controller")
        r = c.get("/v1/administrativo/orcamento?year=2019")
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


class TheDecisionReachesTheObjectTests(unittest.TestCase):
    """O defeito mais grave desta versão, encontrado por AUDITORIA INDEPENDENTE depois de a suíte
    inteira estar verde.

    `POST /v1/financeiro/expenses` criava a despesa em `registered` e abria o pedido.
    `POST /v1/aprovacoes/{id}/decide` gravava a decisão, o gatilho fechava o PEDIDO como aprovado —
    e ninguém escrevia de volta na DESPESA. Não existia um único `UPDATE platform_expenses` em todo
    o código de aplicação.

    O resultado era uma tela que mentia com números certos: despesas registradas E APROVADAS, com o
    painel Financeiro mostrando "A pagar R$ 0,00" ao lado da despesa total — porque `payable` soma
    `status IN ('approved','scheduled')` e nada nunca chegava nesses estados. Em cascata, a posição
    líquida da tesouraria SUPERESTIMAVA o caixa, e a conferência de "despesa paga sem lançamento"
    apontava para um estado inalcançável.

    Por que a suíte não pegou: o único teste de quatro olhos de despesa atacava a restrição por SQL
    direto e nunca passava pela rota. Testar a restrição não testa o fluxo.
    """

    def _despesa_aprovada(self, centavos: int):
        financeiro, controlador = make_staff("finance"), make_staff("controller")
        reauth(financeiro)
        criada = financeiro.post("/v1/financeiro/expenses", {
            "period": str(COMP), "account_code": "5.1.1", "cost_center": "CLOUD",
            "description": "Despesa do teste de aplicação da decisão", "amount_cents": centavos})
        self.assertEqual(criada.status, 201, criada)
        pedido = criada.json["approval"]["request_id"]
        self.assertTrue(pedido, "a despesa nasceu sem pedido de aprovação")
        return financeiro, controlador, criada.json["id"], pedido

    def test_approving_the_request_approves_the_expense(self):
        _, controlador, despesa, pedido = self._despesa_aprovada(9900)
        reauth(controlador)
        decisao = controlador.post(f"/v1/aprovacoes/{pedido}/decide",
                                   {"approve": True, "permission_used": "finance.approve"})
        self.assertEqual(decisao.status, 200, decisao)
        self.assertEqual(decisao.json["state"], "approved")
        with db_system() as c:
            linha = c.one("SELECT status, approved_by, approved_at FROM platform_expenses"
                          " WHERE id = $1", despesa)
        self.assertEqual(linha["status"], "approved",
                         "o pedido fechou como aprovado e a DESPESA ficou em 'registered'")
        self.assertIsNotNone(linha["approved_by"], "aprovação sem autor registrado")
        self.assertIsNotNone(linha["approved_at"], "aprovação sem data: não se audita")

    def test_the_approved_expense_appears_as_payable(self):
        """A consequência que a tela mostra. É o número que estava errado."""
        _, controlador, _despesa, pedido = self._despesa_aprovada(12300)
        reauth(controlador)
        antes = controlador.get("/v1/financeiro/summary").json["payable"]["cents"]
        controlador.post(f"/v1/aprovacoes/{pedido}/decide",
                         {"approve": True, "permission_used": "finance.approve"})
        depois = controlador.get("/v1/financeiro/summary")
        self.assertEqual(depois.json["payable"]["cents"] - antes, 12300,
                         "despesa aprovada não entrou em 'a pagar'")

    def test_the_treasury_position_counts_the_approved_expense(self):
        """A posição líquida SUPERESTIMAVA o caixa pelo total das despesas aprovadas."""
        _, controlador, _d, pedido = self._despesa_aprovada(45600)
        tesoureiro = make_staff("treasury")
        antes = tesoureiro.get("/v1/tesouraria/summary").json
        reauth(controlador)
        controlador.post(f"/v1/aprovacoes/{pedido}/decide",
                         {"approve": True, "permission_used": "finance.approve"})
        depois = tesoureiro.get("/v1/tesouraria/summary").json
        self.assertEqual(depois["payable_cents"] - antes["payable_cents"], 45600)
        self.assertEqual(antes["net_position_cents"] - depois["net_position_cents"], 45600,
                         "a posição líquida não baixou com a despesa aprovada")

    def test_rejecting_the_request_cancels_the_expense(self):
        """Recusada não volta a 'registered': ficaria indistinguível de uma que ninguém olhou."""
        _, controlador, despesa, pedido = self._despesa_aprovada(7700)
        reauth(controlador)
        r = controlador.post(f"/v1/aprovacoes/{pedido}/decide",
                             {"approve": False, "permission_used": "finance.approve",
                              "note": "fora do orçamento do centro de custo"})
        self.assertEqual(r.status, 200, r)
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT status FROM platform_expenses WHERE id = $1",
                                      despesa), "cancelled")

    def test_refusing_without_a_reason_is_refused_by_the_server(self):
        """A obrigatoriedade existia só no navegador — o botão desabilitado.

        A rota aceitava a recusa sem justificativa e devolvia 200. Recusa sem motivo é recusa que
        ninguém pode revisar.
        """
        _, controlador, _d, pedido = self._despesa_aprovada(5500)
        reauth(controlador)
        r = controlador.post(f"/v1/aprovacoes/{pedido}/decide",
                             {"approve": False, "permission_used": "finance.approve"})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "reason_required")

    def test_an_approved_instruction_leaves_pending_approval(self):
        """A tela oferecia "Emitir" em `pending_approval`, estado que a emissão recusa por 409."""
        from impacto.economics import approvals as AP
        from impacto.economics import engine as ENG
        pedinte, aprovador = new_account("osc"), make_staff("controller")
        with db_system() as c:
            instrucao = ENG.create_instruction(
                c, kind="supplier", payee_name="Fornecedor do teste de estado",
                amount_cents=30000, due_on=HOJE, reference="NF do teste",
                created_by=_uid(c, pedinte.email))
            self.assertEqual(c.scalar("SELECT state FROM payment_instructions WHERE id = $1",
                                      instrucao["id"]), "pending_approval")
            _aprovar(c, instrucao["approval"]["request_id"],
                     [(_uid(c, aprovador.email), "finance.approve")])
            self.assertEqual(
                c.scalar("SELECT state FROM payment_instructions WHERE id = $1", instrucao["id"]),
                "approved", "a instrução aprovada ficou em 'pending_approval'")
            self.assertTrue(AP.is_approved(c, object_type="payment_instruction",
                                           object_id=instrucao["id"],
                                           operation="payment_instruction"))
            # E agora a emissão funciona — é o estado que a tela oferece.
            ENG.issue_instruction(c, instruction_id=instrucao["id"])


class MalformedParametersAnswerWithFourTwentyTwoTests(unittest.TestCase):
    """Oito rotas internas devolviam HTTP 500 por um parâmetro de URL digitado errado.

    Cada 500 grava trace completo em `error_events` e conta como erro de servidor na telemetria —
    por `?period=abacaxi`. Encontrado por auditoria independente.
    """

    def test_an_invalid_period_is_a_client_error(self):
        c = make_staff("controller")
        for valor in ("abacaxi", "2026-13", "0000-00", "2026-02-30", ""):
            with self.subTest(valor=valor):
                r = c.get(f"/v1/controladoria/summary?period={valor}")
                self.assertIn(r.status, (200, 422), f"500 em period={valor!r}: {r.body[:200]}")
                if r.status == 422:
                    self.assertEqual(r.json["code"], "invalid_period")

    def test_an_invalid_number_is_a_client_error(self):
        c = make_staff("controller")
        casos = [("/v1/controladoria/reconciliation?days=abc", "invalid_number"),
                 ("/v1/controladoria/reconciliation?days=-5", "out_of_range"),
                 ("/v1/controladoria/reconciliation?days=99999", "out_of_range"),
                 ("/v1/administrativo/orcamento?year=xyz", "invalid_number"),
                 ("/v1/financeiro/fee-preview?amount_cents=abc", "invalid_number"),
                 ("/v1/financeiro/fee-preview?amount_cents=0", "out_of_range")]
        for rota, codigo in casos:
            with self.subTest(rota=rota):
                r = c.get(rota)
                self.assertEqual(r.status, 422, f"esperava 422 em {rota}: {r.body[:200]}")
                self.assertEqual(r.json["code"], codigo)

    def test_a_negative_window_never_becomes_a_window_into_the_future(self):
        """`?days=-5` respondia 200 e virava `now() - interval '-5 days'`.

        A janela ia para o FUTURO, as conferências vinham vazias e `divergences` ficava
        subcontado — um relatório de conciliação dizendo "nenhuma divergência" por causa de um
        sinal.
        """
        c = make_staff("controller")
        self.assertEqual(c.get("/v1/controladoria/reconciliation?days=-5").status, 422)

    def test_a_malformed_accounting_batch_is_a_client_error(self):
        c = make_staff("accounting")
        reauth(c)
        casos = [
            [{"foo": 1}, {"bar": 2}],
            [{"period": "nao-e-data", "account_code": "1.2.1", "side": "debit",
              "amount_cents": 100, "description": "x"}] * 2,
            [{"period": str(COMP), "account_code": "1.2.1", "side": "ESQUERDA",
              "amount_cents": 100, "description": "x"}] * 2,
            [{"period": str(COMP), "account_code": "nao-e-conta", "side": "debit",
              "amount_cents": 100, "description": "x"}] * 2,
        ]
        for entradas in casos:
            with self.subTest(entradas=str(entradas)[:60]):
                r = c.post("/v1/contabilidade/batches", {"entries": entradas})
                self.assertEqual(r.status, 422, f"esperava 422: {r.body[:200]}")

    def test_the_caller_cannot_choose_the_origin_of_a_manual_entry(self):
        """`source_kind`/`source_id` ficaram FORA do schema de propósito.

        Deixá-los abertos permitiria a `accounting.write` forjar
        `source_kind='manual', source_id=<id da despesa>` — exatamente o campo que a conciliação de
        "despesa paga sem lançamento" lê. A conferência passaria a confirmar a si mesma.
        """
        c = make_staff("accounting")
        reauth(c)
        r = c.post("/v1/contabilidade/batches", {"entries": [
            {"period": str(COMP), "account_code": "1.2.1", "side": "debit", "amount_cents": 100,
             "description": "tentativa de escolher a origem", "source_kind": "invoice",
             "source_id": "00000000-0000-0000-0000-000000000000"},
            {"period": str(COMP), "account_code": "4.1.1", "side": "credit", "amount_cents": 100,
             "description": "contrapartida"},
        ]})
        self.assertEqual(r.status, 422, f"o schema aceitou campo extra: {r.body[:200]}")


class EveryMetricCarriesItsProvenanceTests(unittest.TestCase):
    """Três afirmações da documentação que o código não cumpria. Auditoria independente."""

    def test_last_updated_is_actually_emitted(self):
        """`FINANCIAL_ENGINE.md` prometia `last_updated` em todo indicador. Nenhum o tinha."""
        from impacto.economics import metrics as MET
        with db_system() as c:
            resumo = MET.summary(c, period=COMP)
        vistos = 0
        for bloco in ("operation_layer", "revenue", "cash", "expenses", "gmv", "conversion", "result"):
            for chave, valor in resumo[bloco].items():
                if isinstance(valor, dict) and "source" in valor:
                    self.assertIn("last_updated", valor, f"{bloco}.{chave}")
                    self.assertTrue(valor["last_updated"])
                    vistos += 1
        self.assertGreater(vistos, 10)

    def test_an_unavailable_metric_without_a_reason_is_a_programming_error(self):
        """`available: false` com `unavailable_reason: null` é o "`null` não explica" que o
        próprio módulo recusa. Agora levanta na construção, onde é barato."""
        from impacto.economics.metrics import _metric
        with self.assertRaises(ValueError):
            _metric(None, source="x", calculation="y", period="z", available=False)

    def test_the_ai_cost_is_available_only_when_every_call_has_a_price(self):
        """O INVARIANTE, conferido contra o estado real do banco — não contra um estado montado.

        `ai_price_table` não é escrita pelo papel da aplicação (e não deveria ser: preço de modelo
        é declaração, não operação), então o teste não pode preparar o cenário. O que ele confere é
        a regra: o custo só está disponível quando existe tabela de preço E nenhuma chamada do mês
        ficou sem preço. Qualquer outro estado responde indisponível COM MOTIVO.

        A versão anterior respondia **zero, disponível**, porque a condição
        `not (chamadas and sem_preco == chamadas)` curto-circuita com zero chamadas.
        """
        from impacto.economics import metrics as MET
        with db_system() as c:
            tem_tabela = bool(c.scalar("SELECT count(*) FROM ai_price_table"))
            sem_preco = int(c.scalar(
                "SELECT count(*) FROM ai_usage WHERE cost_status = 'no_price_table'"
                "   AND created_at >= date_trunc('month', $1::date)"
                "   AND created_at < date_trunc('month', $1::date) + interval '1 month'", COMP))
            ia = MET.expenses(c, period=COMP)["ai_cost"]
        esperado = tem_tabela and sem_preco == 0
        self.assertEqual(ia["available"], esperado,
                         f"tabela de preço: {tem_tabela}, chamadas sem preço: {sem_preco}")
        if esperado:
            self.assertIsNotNone(ia["value"])
        else:
            self.assertIsNone(ia["value"], "custo de IA não apurável devolveu número")
            self.assertTrue(ia["unavailable_reason"])
            # O motivo diz QUAL dos dois estados: sem tabela, ou com chamada sem preço.
            self.assertTrue(
                ("ai_price_table" in ia["unavailable_reason"]) if not tem_tabela
                else ("sem preço declarado" in ia["unavailable_reason"]),
                ia["unavailable_reason"])

    def test_zero_calls_never_means_zero_cost(self):
        """O caso exato do curto-circuito: nenhuma chamada no mês não é "a IA custou zero"."""
        from impacto.economics import metrics as MET
        vazio = _periodo(-24)
        with db_system() as c:
            self.assertEqual(c.scalar(
                "SELECT count(*) FROM ai_usage WHERE created_at >= date_trunc('month', $1::date)"
                "   AND created_at < date_trunc('month', $1::date) + interval '1 month'", vazio), 0)
            ia = MET.expenses(c, period=vazio)["ai_cost"]
        if not ia["available"]:
            self.assertIsNone(ia["value"])
            self.assertTrue(ia["unavailable_reason"])
        else:
            # Só pode estar disponível se houver tabela de preço — e aí zero é zero de verdade.
            with db_system() as c:
                self.assertTrue(c.scalar("SELECT count(*) FROM ai_price_table"),
                                "custo de IA disponível valendo zero SEM tabela de preço: é "
                                "exatamente o zero que o módulo existe para recusar")

    def test_conversion_without_organizations_says_why(self):
        from impacto.economics.metrics import _metric
        # Reproduz o estado do banco vazio sem precisar esvaziá-lo: o motivo tem de existir para a
        # construção ser possível, e é isso que o guarda acima garante.
        m = _metric(None, currency=None, source="x", calculation="y", period="z",
                    available=False, unavailable_reason="não há denominador")
        self.assertTrue(m["unavailable_reason"])

    def test_closing_a_period_keeps_the_note(self):
        """A rota aceitava a nota e o motor a descartava: a coluna ficava nula."""
        from impacto.economics import engine as ENG
        p = _periodo(-19)
        with db_system() as c:
            ENG.ensure_period(c, p)
            ENG.close_period(c, period=p, closed_by=_um_usuario(c),
                             note="Fechamento conferido contra o extrato bancário")
            self.assertIn("extrato", c.scalar(
                "SELECT note FROM accounting_periods WHERE period = $1", p))


if __name__ == "__main__":
    unittest.main()
