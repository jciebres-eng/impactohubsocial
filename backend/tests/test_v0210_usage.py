"""Motor de uso: contadores, alertas de 70/90/100% e teto de gasto.

O DEFEITO HISTÓRICO QUE A PRIMEIRA CLASSE TRAVA

Havia duas contagens para a MESMA cota de IA. O bloqueio (`gateway._check_quota`) excluía pedidos
recusados; o painel (`GET /v1/ai/usage`) não. A pessoa via "80 de 100" numa tela que o bloqueio
contava como 60, e planejava o mês com um número que não era o que a limitava. Nenhuma das duas
estava errada sozinha — o defeito era existirem duas.
"""
from __future__ import annotations

import unittest

from tests.support import db_system, new_account


def scalar(sql, *a):
    with db_system() as c:
        return c.scalar(sql, *a)


class OneCountForTheAiQuotaTests(unittest.TestCase):

    def test_a_rejected_request_does_not_consume_quota_anywhere(self):
        cli = new_account("osc")
        with db_system() as c:
            for st in ("ok", "ok", "rejected"):
                c.run("INSERT INTO ai_usage(org_id, feature, provider, status)"
                      " VALUES ($1,'draft','stub',$2)", cli.org_id, st)
        # A função única: dois pedidos atendidos, o recusado não conta — a pessoa não recebeu nada.
        self.assertEqual(scalar("SELECT ai_usage_this_month($1)", cli.org_id), 2)
        painel = cli.get("/v1/ai/usage")
        self.assertEqual(painel.status, 200, painel.body)
        # v0.23.0 — o painel passou a separar COTA (chamadas), ORÇAMENTO (dinheiro) e CRÉDITO
        # (unidade comercial), porque são três controles diferentes e qualquer um pode barrar uma
        # chamada. O número da cota continua vindo da mesma função que bloqueia; o que mudou é o
        # lugar dele na resposta.
        self.assertEqual(painel.json["quota"]["used_this_month"], 2,
                         "o painel voltou a contar diferente do bloqueio")
        self.assertEqual("chamadas", painel.json["quota"]["counts"],
                         "a cota conta CHAMADAS, e a resposta tem de dizer isso: chamada não é "
                         "unidade de custo, e confundir as duas foi o defeito que o orçamento "
                         "em dinheiro corrige")

    def test_the_panel_and_the_block_read_the_same_function(self):
        """Nenhuma segunda contagem de cota mensal de IA fora de `ai_usage_this_month()`.

        A v0.23.0 precisou apertar este guarda. A primeira versão procurava duas frases no MESMO
        ARQUIVO — `FROM ai_usage WHERE org_id` e `date_trunc('month'` — e reprovava por
        coincidência: a central de IA tem um recorte de 30 dias sobre `ai_usage` e, noutra consulta
        do mesmo arquivo, a competência do ORÇAMENTO. Nenhuma das duas é contagem de cota.

        Guarda que reprova por coincidência é guarda que alguém afrouxa, e aí ele deixa de proteger.
        A conferência agora é por INSTRUÇÃO: o Python junta literais adjacentes em tempo de análise,
        então cada constante de texto na árvore é uma consulta inteira. A reprovação exige as três
        marcas na MESMA consulta — contagem, `ai_usage` e recorte de mês.
        """
        import ast
        import pathlib
        raiz = pathlib.Path(__file__).resolve().parents[1] / "impacto"
        copias = []
        for f in raiz.rglob("*.py"):
            arvore = ast.parse(f.read_text(encoding="utf-8"))
            for no in ast.walk(arvore):
                if not (isinstance(no, ast.Constant) and isinstance(no.value, str)):
                    continue
                sql = no.value.lower()
                # As QUATRO marcas juntas. `org_id` é a que separa cota de ORGANIZAÇÃO de custo
                # da PLATAFORMA: `economics/metrics.py` conta chamadas de IA por mês para apurar
                # despesa da plataforma inteira, sem recorte de inquilino, e isso é outra pergunta.
                if ("ai_usage" in sql and "count(" in sql and "org_id" in sql
                        and ("date_trunc('month'" in sql or "current_date)" in sql)):
                    copias.append(f"{f.relative_to(raiz)}:{no.lineno}")
        self.assertEqual(copias, [],
                         "voltou a existir contagem de cota de IA fora de ai_usage_this_month(): "
                         + ", ".join(copias))

    def test_the_tightened_guard_would_still_catch_a_real_duplicate(self):
        """Contraprova: um guarda apertado só vale se ainda souber reprovar a cópia de verdade."""
        duplicata = ("SELECT count(*) FROM ai_usage WHERE org_id = $1"
                     " AND date_trunc('month', created_at) = date_trunc('month', current_date)")
        sql = duplicata.lower()
        self.assertTrue("ai_usage" in sql and "count(" in sql and "org_id" in sql
                        and "date_trunc('month'" in sql,
                        "a regra do guarda deixaria passar uma segunda contagem de cota")
        # E a contraprova do outro lado: a despesa da PLATAFORMA (sem `org_id`) não é cota e não
        # pode ser reprovada, senão o guarda obrigaria a apagar a apuração de custo.
        despesa = ("SELECT count(*) FROM ai_usage WHERE created_at >= "
                   "date_trunc('month', $1::date)").lower()
        self.assertNotIn("org_id", despesa)


class CounterMirrorsTheLiveCountTests(unittest.TestCase):

    def test_the_counter_matches_what_actually_blocks(self):
        cli = new_account("osc")
        with db_system() as c:
            for _ in range(3):
                c.run("INSERT INTO ai_usage(org_id, feature, provider, status)"
                      " VALUES ($1,'draft','stub','ok')", cli.org_id)
        r = cli.get("/v1/commercial/usage")
        self.assertEqual(r.status, 200, r.body)
        ia = [m for m in r.json["metrics"] if m["metric"] == "ai_requests_month"][0]
        self.assertEqual(ia["used"], 3)
        self.assertEqual(ia["used"], scalar("SELECT ai_usage_this_month($1)", cli.org_id))
        # E ficou gravado: a contagem ao vivo não sobrevive à retenção, o contador sim.
        self.assertEqual(scalar("SELECT used FROM usage_counters WHERE org_id = $1"
                                " AND metric = 'ai_requests_month'", cli.org_id), 3)

    def test_every_declared_metric_has_a_human_label(self):
        from impacto.services import usage as U
        for metric, rotulo in U.METRICS.items():
            self.assertTrue(rotulo and not rotulo.startswith(metric),
                            f"{metric} não tem rótulo legível")

    def test_every_declared_metric_can_actually_be_counted(self):
        # Uma métrica declarada sem contagem apareceria na tela como erro 500 no primeiro acesso.
        from impacto.services import usage as U
        cli = new_account("osc")
        with db_system() as c:
            for metric in U.METRICS:
                self.assertIsInstance(U._live(c, cli.org_id, metric), int)

    def test_an_unknown_metric_is_refused_instead_of_counted_as_zero(self):
        from impacto.services import usage as U
        cli = new_account("osc")
        with db_system() as c:
            with self.assertRaises(ValueError):
                U._live(c, cli.org_id, "metrica_que_nao_existe")


class ThresholdAlertTests(unittest.TestCase):

    def _com_consumo(self, usados: int):
        cli = new_account("osc")
        with db_system() as c:
            # Limite de IA do plano básico da OSC, para calcular o percentual esperado.
            from impacto.services.entitlements import effective
            lim = effective(c, cli.org_id, "osc")["limits"].get("ai_requests_month")
            for _ in range(usados):
                c.run("INSERT INTO ai_usage(org_id, feature, provider, status)"
                      " VALUES ($1,'draft','stub','ok')", cli.org_id)
        return cli, lim

    def test_seventy_percent_warns_without_blocking(self):
        cli, lim = self._com_consumo(0)
        self.assertIsNotNone(lim, "o plano precisa ter limite para o teste valer")
        with db_system() as c:
            for _ in range(int(lim * 0.72)):
                c.run("INSERT INTO ai_usage(org_id, feature, provider, status)"
                      " VALUES ($1,'draft','stub','ok')", cli.org_id)
            from impacto.services import usage as U
            U.check_alerts(c, cli.org_id, "osc")
        limiares = [r["threshold"] for r in _alertas(cli.org_id)]
        self.assertEqual(limiares, [70])
        corpo = scalar("SELECT body FROM notifications WHERE org_id = $1"
                       " AND kind = 'billing.usage_threshold'", cli.org_id)
        self.assertIn("não um bloqueio", corpo)

    def test_each_threshold_fires_once_per_period(self):
        cli, lim = self._com_consumo(0)
        with db_system() as c:
            for _ in range(lim):
                c.run("INSERT INTO ai_usage(org_id, feature, provider, status)"
                      " VALUES ($1,'draft','stub','ok')", cli.org_id)
            from impacto.services import usage as U
            U.check_alerts(c, cli.org_id, "osc")
            U.check_alerts(c, cli.org_id, "osc")      # segunda passagem: não duplica
            U.check_alerts(c, cli.org_id, "osc")
        limiares = sorted(r["threshold"] for r in _alertas(cli.org_id))
        self.assertEqual(limiares, [70, 90, 100],
                         "os três limiares deveriam ter saído uma vez cada")
        n = scalar("SELECT count(*) FROM notifications WHERE org_id = $1"
                   " AND kind = 'billing.usage_threshold'", cli.org_id)
        self.assertEqual(n, 3, f"{n} avisos para três limiares — o job repetiria isso toda hora")

    def test_reaching_the_limit_says_nothing_extra_was_charged(self):
        cli, lim = self._com_consumo(0)
        with db_system() as c:
            for _ in range(lim):
                c.run("INSERT INTO ai_usage(org_id, feature, provider, status)"
                      " VALUES ($1,'draft','stub','ok')", cli.org_id)
            from impacto.services import usage as U
            U.check_alerts(c, cli.org_id, "osc")
        # Os três avisos nascem no mesmo instante, então ordenar por data não escolhe nada. O teste
        # procura o aviso de 100% pelo conteúdo dele.
        corpos = [r["body"] for r in _notificacoes(cli.org_id)]
        cheio = [b for b in corpos if "atingiu o limite" in b or "Nada foi cobrado" in b]
        self.assertTrue(cheio, f"nenhum aviso de limite atingido entre: {corpos}")
        self.assertIn("Nada foi cobrado a mais", cheio[0])
        self.assertIn("interrompe o excedente", cheio[0])

    def test_no_alert_below_seventy_percent(self):
        cli, lim = self._com_consumo(0)
        with db_system() as c:
            for _ in range(int(lim * 0.5)):
                c.run("INSERT INTO ai_usage(org_id, feature, provider, status)"
                      " VALUES ($1,'draft','stub','ok')", cli.org_id)
            from impacto.services import usage as U
            U.check_alerts(c, cli.org_id, "osc")
        self.assertEqual(_alertas(cli.org_id), [])


def _notificacoes(org_id):
    with db_system() as c:
        return [dict(r) for r in c.query(
            "SELECT body FROM notifications WHERE org_id = $1"
            " AND kind = 'billing.usage_threshold'", org_id)]


def _alertas(org_id):
    with db_system() as c:
        return [dict(r) for r in c.query(
            "SELECT threshold FROM usage_alerts WHERE org_id = $1 ORDER BY threshold", org_id)]


class SpendLimitTests(unittest.TestCase):

    def test_the_organization_sets_its_own_limit(self):
        cli = new_account("osc")
        r = cli.put("/v1/commercial/spend-limit", {"limit_cents": 50000, "action": "hard_stop"})
        self.assertEqual(r.status, 200, r.body)
        self.assertEqual(r.json["limit_cents"], 50000)
        self.assertEqual(cli.get("/v1/commercial/usage").json["spend_limit"]["action"], "hard_stop")

    def test_hard_stop_refuses_the_charge_before_it_happens(self):
        from impacto.http import ApiError
        from impacto.services import usage as U
        cli = _autorizada()
        with db_system() as c:
            U.set_spend_limit(c, org_id=cli.org_id, limit_cents=10000, action="hard_stop",
                              set_by=None)
            with self.assertRaises(ApiError) as e:
                U.enforce(c, cli.org_id, 79900)
        self.assertEqual(e.exception.code, "spend_limit_reached")
        self.assertIn("interrompida antes de acontecer", e.exception.message)
        self.assertEqual(scalar("SELECT count(*) FROM platform_charges WHERE org_id = $1",
                                cli.org_id), 0, "o hard_stop deixou passar uma cobrança")

    def test_warn_lets_it_through_and_notifies(self):
        from impacto.services import usage as U
        cli = _autorizada()
        with db_system() as c:
            U.set_spend_limit(c, org_id=cli.org_id, limit_cents=10000, action="warn", set_by=None)
            U.enforce(c, cli.org_id, 79900)      # não levanta
        corpo = scalar("SELECT body FROM notifications WHERE org_id = $1"
                       " AND kind = 'billing.spend_limit_warning'", cli.org_id)
        self.assertIsNotNone(corpo, "o modo avisar não avisou")
        self.assertIn("nada foi interrompido", corpo)

    def test_no_limit_means_no_interference(self):
        from impacto.services import usage as U
        cli = new_account("osc")
        with db_system() as c:
            U.enforce(c, cli.org_id, 10_000_000)      # sem teto definido: segue
            self.assertFalse(U.would_exceed(c, cli.org_id, 10_000_000)["exceeds"])

    def test_simulated_charges_do_not_count_toward_the_limit(self):
        """Um ambiente de teste não pode disparar o hard_stop de um cliente real.

        As duas cobranças abaixo percorrem o MESMO caminho de estados — a de verdade e a simulada.
        Só o que as separa é `is_simulated`, que é precisamente o que o teste quer provar que basta.
        """
        from impacto.economics import payments as PAY
        from impacto.services import usage as U
        cli = _autorizada()
        with db_system() as c:
            ids = {}
            # `is_simulated` é DERIVADA do provedor por gatilho (v0.17.0) e não se escreve à mão:
            # `stripe` é real, qualquer outro é simulado. É por isso que o teste troca o PROVEDOR
            # em vez de a coluna — e é a mesma derivação que a exigência de autorização consulta.
            for rotulo, provedor in (("real", "stripe"), ("simulada", "sandbox")):
                ids[rotulo] = c.scalar(
                    "INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                    " currency)"
                    " VALUES ($1,'subscription','card',$2,500000,'BRL') RETURNING id::text",
                    cli.org_id, provedor)
                # O caminho real do grafo: a pessoa inicia o checkout, a cobrança fica pendente e
                # o provedor confirma. As duas últimas são de origem `webhook` (org_id nulo) —
                # inventar um atalho aqui testaria um caminho que produção não tem.
                PAY.transition(c, charge_id=ids[rotulo], to_state="checkout_started",
                               org_id=cli.org_id)
                PAY.transition(c, charge_id=ids[rotulo], to_state="pending", org_id=cli.org_id)
                PAY.transition(c, charge_id=ids[rotulo], to_state="paid")
            # Duas cobranças pagas de R$ 5.000; só a de verdade entra no teto.
            self.assertEqual(U.spent_this_month(c, cli.org_id), 500000)

    def test_an_organization_cannot_read_another_organizations_limit(self):
        dona = new_account("osc")
        dona.put("/v1/commercial/spend-limit", {"limit_cents": 12345, "action": "warn"})
        outra = new_account("osc")
        self.assertIsNone(outra.get("/v1/commercial/usage").json["spend_limit"]["limit_cents"])


def _autorizada():
    """Conta com autorização de cobrança vigente — exigida pelo gatilho antes de qualquer cobrança."""
    cli = new_account("osc")
    r = cli.post("/v1/commercial/offers",
                 {"plan_key": "osc_premium", "interval": "month",
                  "billing_frequency": "recurring", "payment_method": "card"})
    cli.post(f"/v1/commercial/offers/{r.json['id']}/accept", {"consent_status": "authorized"})
    return cli


class IdempotencyKeyTests(unittest.TestCase):

    def test_the_same_key_twice_creates_one_charge(self):
        cli = _autorizada()
        with db_system() as c:
            c.run("INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                  " currency, idempotency_key)"
                  " VALUES ($1,'subscription','card','sandbox',79900,'BRL','pedido-abc-123')",
                  cli.org_id)
        with self.assertRaises(Exception) as e:
            with db_system() as c:
                c.run("INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                      " currency, idempotency_key)"
                      " VALUES ($1,'subscription','card','sandbox',79900,'BRL','pedido-abc-123')",
                      cli.org_id)
        self.assertIn("ux_charge_idempotency", str(e.exception))
        self.assertEqual(scalar("SELECT count(*) FROM platform_charges WHERE org_id = $1",
                                cli.org_id), 1)

    def test_the_key_is_scoped_per_organization(self):
        # Duas organizações podem escolher a mesma string sem colidir — e, o que importa mais, uma
        # não descobre a chave da outra por conflito de inserção.
        a, b = _autorizada(), _autorizada()
        with db_system() as c:
            for org in (a.org_id, b.org_id):
                c.run("INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                      " currency, idempotency_key)"
                      " VALUES ($1,'subscription','card','sandbox',79900,'BRL','fatura-1')", org)
        self.assertEqual(scalar("SELECT count(*) FROM platform_charges"
                                " WHERE idempotency_key = 'fatura-1'"), 2)
