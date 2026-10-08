"""Período gratuito: fronteira temporal, meses de calendário e fuso comercial.

POR QUE ESTES TESTES SÃO ESCRITOS ASSIM

O defeito que eles procuram aparece em uma janela de poucos segundos por ano. Um teste rodando ao
meio-dia de um dia qualquer passa com a implementação errada e com a certa. Então aqui o relógio
não é esperado: ele é POSICIONADO, movendo as datas do dado para encostar na fronteira, e a
pergunta é feita exatamente a 2, a 1 e a 0 segundos dela.

A convenção de `ends_at` é EXCLUSIVA: o período é [started_at, ends_at). "Gratuito até 31/12/2026
23:59:59" é gravado como ends_at = 2027-01-01 00:00:00 America/Sao_Paulo. Escrever 23:59:59
literalmente deixaria 23:59:59,5 sem classificação — nem gratuito, nem pago.
"""
from __future__ import annotations

import unittest

from tests.support import Client, db_system, new_account, owner_conn


def q1(sql, *a):
    with db_system() as c:
        return c.one(sql, *a)


def scalar(sql, *a):
    with db_system() as c:
        return c.scalar(sql, *a)


class CalendarMonthsTests(unittest.TestCase):
    """Três meses são TRÊS MESES DE CALENDÁRIO, não noventa dias.

    A diferença não é acadêmica: 90 dias a partir de 01/01 terminam em 01/04 (ano comum), mas
    90 dias a partir de 01/03 terminam em 30/05 — e o cliente que assinou dia 1º espera dia 1º nos
    dois casos. Quem assina em meses longos recebe MENOS com a regra de 90 dias, e percebe.
    """

    def _add(self, iso: str, meses: int) -> str:
        return scalar("SELECT to_char(add_calendar_months($1::timestamptz, $2)"
                      " AT TIME ZONE commercial_tz(), 'YYYY-MM-DD HH24:MI')", iso, meses)

    def test_three_months_lands_on_the_same_day_number(self):
        self.assertEqual(self._add("2027-01-15 10:30-03", 3), "2027-04-15 10:30")
        self.assertEqual(self._add("2027-02-01 00:00-03", 3), "2027-05-01 00:00")

    def test_a_day_that_does_not_exist_in_the_target_month_sticks_to_the_last_one(self):
        # 31/01 + 3 meses = 30/04, porque abril não tem 31. A alternativa (01/05) daria ao cliente
        # um dia a mais de graça em silêncio, e tornaria o fim do período dependente do mês em que
        # ele assinou — que é justamente o que a regra de meses de calendário evita.
        self.assertEqual(self._add("2027-01-31 09:00-03", 3), "2027-04-30 09:00")
        self.assertEqual(self._add("2026-11-30 09:00-03", 3), "2027-02-28 09:00")
        self.assertEqual(self._add("2027-11-30 09:00-03", 3), "2028-02-29 09:00")   # bissexto

    def _noventa(self, iso: str) -> str:
        return scalar("SELECT to_char(($1::timestamptz + interval '90 days')"
                      " AT TIME ZONE commercial_tz(), 'YYYY-MM-DD HH24:MI')", iso)

    def test_ninety_days_sometimes_coincides_with_three_months_which_is_the_trap(self):
        # Janeiro+fevereiro+março de 2027 somam exatamente 31+28+31 = 90 dias. Quem testar a regra
        # de 90 dias com uma assinatura de 1º de janeiro verá os dois métodos concordarem e
        # concluirá que são equivalentes. Não são — eles coincidem num trimestre em três.
        self.assertEqual(self._noventa("2027-01-01 12:00-03"), "2027-04-01 12:00")
        self.assertEqual(self._add("2027-01-01 12:00-03", 3), "2027-04-01 12:00")

    def test_ninety_days_and_three_months_diverge_in_most_quarters(self):
        # E aqui a armadilha se desfaz: nos dois casos abaixo a regra de 90 dias entrega DOIS dias
        # a menos de gratuidade do que o cliente espera, e sempre para menos — porque trimestres
        # com meses de 31 dias são a maioria.
        for inicio, meses, noventa in (("2027-03-01 12:00-03", "2027-06-01 12:00", "2027-05-30 12:00"),
                                       ("2027-05-01 12:00-03", "2027-08-01 12:00", "2027-07-30 12:00")):
            self.assertEqual(self._add(inicio, 3), meses)
            self.assertEqual(self._noventa(inicio), noventa)
            self.assertNotEqual(self._noventa(inicio), meses)

    def test_the_subscription_grant_was_retired_with_the_subscription(self):
        """v0.27.0 (ADR-341): não há '3 meses de assinatura nova' porque não há assinatura."""
        from impacto.services import free_period as FP
        self.assertFalse(hasattr(FP, "NEW_SUBSCRIPTION_MONTHS"))
        self.assertFalse(hasattr(FP, "grant_new_subscription"))
        self.assertNotIn("2027_NEW_SUBSCRIPTION", FP.SOURCES)


class CampaignBoundaryTests(unittest.TestCase):
    """A virada 2026 → 2027, no fuso comercial, segundo a segundo."""

    def test_the_campaign_ends_at_midnight_of_january_first_in_sao_paulo(self):
        self.assertEqual(
            scalar("SELECT to_char(full_free_2026_ends_at() AT TIME ZONE commercial_tz(),"
                   " 'YYYY-MM-DD HH24:MI:SS')"),
            "2027-01-01 00:00:00")

    def test_the_commercial_timezone_is_sao_paulo_and_not_utc(self):
        self.assertEqual(scalar("SELECT commercial_tz()"), "America/Sao_Paulo")
        # O instante guardado é UTC — o fuso comercial vive na fronteira, não no armazenamento.
        self.assertEqual(scalar("SELECT to_char(full_free_2026_ends_at() AT TIME ZONE 'UTC',"
                                " 'YYYY-MM-DD HH24:MI:SS')"),
                         "2027-01-01 03:00:00")

    def test_the_last_seconds_of_2026_are_still_free_and_the_first_of_2027_are_not(self):
        casos = [("2026-12-31 23:59:58", True),
                 ("2026-12-31 23:59:59", True),
                 ("2027-01-01 00:00:00", False),   # ends_at é EXCLUSIVO
                 ("2027-01-01 00:00:01", False)]
        for local, gratuito in casos:
            dentro = scalar(
                "SELECT (($1::timestamp AT TIME ZONE commercial_tz()) < full_free_2026_ends_at())",
                local)
            self.assertIs(dentro, gratuito,
                          f"{local} em São Paulo deveria estar {'dentro' if gratuito else 'fora'}"
                          " da campanha FULL FREE 2026")

    def test_nine_pm_utc_on_december_31_is_still_2026_in_sao_paulo(self):
        # 2026-12-31 21:00 UTC = 2026-12-31 18:00 em São Paulo. Um sistema que comparasse a data
        # UTC com '2026-12-31' acertaria aqui; o erro aparece às 02:00 UTC do dia 1º, que ainda é
        # 23:00 do dia 31 em São Paulo — o caso seguinte.
        self.assertTrue(scalar("SELECT '2026-12-31 21:00:00+00'::timestamptz < full_free_2026_ends_at()"))

    def test_two_am_utc_on_january_first_is_still_december_31_in_sao_paulo(self):
        # ESTE é o caso que separa as duas implementações. Às 02:00 UTC do dia 1º, quem comparar
        # com a data UTC já cortou a gratuidade de todo mundo — três horas antes da virada real.
        self.assertTrue(scalar("SELECT '2027-01-01 02:00:00+00'::timestamptz < full_free_2026_ends_at()"))
        self.assertFalse(scalar("SELECT '2027-01-01 03:00:00+00'::timestamptz < full_free_2026_ends_at()"))


class CalendarGrantDateTests(unittest.TestCase):
    """Cinco datas de concessão de três meses de calendário (a aritmética continua valendo para concessões)."""

    def test_the_five_requested_grant_dates(self):
        casos = [("2027-01-01", "2027-04-01"),
                 ("2027-02-01", "2027-05-01"),
                 ("2027-02-15", "2027-05-15"),
                 ("2027-02-28", "2027-05-28"),
                 ("2027-03-31", "2027-06-30")]   # junho não tem 31
        for inicio, fim in casos:
            got = scalar("SELECT to_char(add_calendar_months(($1 || ' 10:00')::timestamp"
                         " AT TIME ZONE commercial_tz(), 3) AT TIME ZONE commercial_tz(),"
                         " 'YYYY-MM-DD')", inicio)
            self.assertEqual(got, fim, f"concessão em {inicio} deveria terminar em {fim}")


class SignupGrantsTheCampaignTests(unittest.TestCase):
    """Cadastrar concede o período gratuito — por conta, com motivo e versão."""

    def test_a_new_account_gets_an_individual_record_not_a_global_date(self):
        cli = new_account("osc")
        row = q1("SELECT source, status, reason, pricing_version, months, started_at, ends_at"
                 " FROM free_periods WHERE org_id = $1", cli.org_id)
        self.assertIsNotNone(row, "o cadastro não concedeu período gratuito")
        self.assertEqual(row["source"], "2026_CAMPAIGN")
        self.assertEqual(row["status"], "active")
        self.assertIn("FULL FREE 2026", row["reason"])
        # A versão de preço gravada é a REGRA que concedeu a gratuidade — a campanha FULL FREE 2026
        # está escrita na PRICING_BIBLE.md, que é a Pricing Version 2027.01. Não é o que a pessoa
        # aceitou: aceite mora em `offer_acceptances`, e esta conta não aceitou nada.
        from impacto.services import free_period as FP
        self.assertEqual(row["pricing_version"], FP.pricing_version())
        self.assertEqual(row["pricing_version"], "2027.02")
        self.assertIsNone(row["months"], "campanha tem data fixa, não contagem de meses")

    def test_the_campaign_is_granted_once_per_account(self):
        cli = new_account("company")
        with db_system() as c:
            from impacto.services import free_period as FP
            self.assertIsNone(FP.grant_campaign_2026(c, org_id=cli.org_id),
                              "a segunda concessão da mesma campanha deveria ser recusada")
        self.assertEqual(scalar("SELECT count(*) FROM free_periods WHERE org_id = $1"
                                " AND source = '2026_CAMPAIGN'", cli.org_id), 1)

    def test_free_period_end_is_published_by_the_backend(self):
        cli = new_account("osc")
        r = cli.get("/v1/commercial/state")
        self.assertEqual(r.status, 200, r.body)
        self.assertIsNotNone(r.json["free_period_end"], "FREE_PERIOD_END não foi publicado")
        self.assertIn(r.json["state"], ("FREE_GRANT", "GRANT_EXPIRING"))
        self.assertFalse(r.json["charge_authorized"])
        self.assertFalse(r.json["will_be_charged"])
        self.assertIn("Nenhuma cobrança", r.json["on_expiry"])


class NoGlobalDateInCodeTests(unittest.TestCase):
    """A data da campanha mora no banco, não espalhada pelo código de produto."""

    def test_the_campaign_date_is_not_hardcoded_across_the_product(self):
        import pathlib
        raiz = pathlib.Path(__file__).resolve().parents[1] / "impacto"
        culpados = []
        for f in raiz.rglob("*.py"):
            texto = f.read_text(encoding="utf-8")
            for n, linha in enumerate(texto.splitlines(), 1):
                if "2026-12-31" in linha or "2027-01-01" in linha:
                    culpados.append(f"{f.relative_to(raiz)}:{n}")
        self.assertEqual(culpados, [],
                         "a fronteira da campanha deve vir de full_free_2026_ends_at(), não de "
                         "uma data escrita no código: " + ", ".join(culpados))

    def test_the_web_app_never_computes_the_end_of_the_free_period(self):
        import pathlib
        web = pathlib.Path(__file__).resolve().parents[2] / "web" / "src"
        if not web.exists():
            self.skipTest("frontend ausente")
        culpados = []
        for f in list(web.rglob("*.tsx")) + list(web.rglob("*.ts")):
            texto = f.read_text(encoding="utf-8")
            for n, linha in enumerate(texto.splitlines(), 1):
                if "2026-12-31" in linha or "2027-01-01" in linha:
                    culpados.append(f"{f.relative_to(web)}:{n}")
        self.assertEqual(culpados, [],
                         "o frontend deve LER free_period_end do backend, nunca calcular a data: "
                         + ", ".join(culpados))


class GrantIsImmutableTests(unittest.TestCase):
    """Concessão é fato. Encurtar o que o cliente recebeu não é uma alteração: é uma reescrita."""

    def test_the_end_date_cannot_be_rewritten_even_by_the_owner(self):
        cli = new_account("osc")
        pid = scalar("SELECT id::text FROM free_periods WHERE org_id = $1", cli.org_id)
        # Em contexto de SISTEMA, que é o caminho mais privilegiado que a aplicação tem.
        with self.assertRaises(Exception) as e:
            with db_system() as c:
                c.run("UPDATE free_periods SET ends_at = now() WHERE id = $1", pid)
        self.assertIn("não se altera", str(e.exception))
        # E o DONO da tabela também não escapa. É aqui que o gatilho ganha do RLS: políticas de
        # linha não se aplicam ao dono (e não podem, porque é o dono que roda o `pg_dump`), mas o
        # gatilho dispara para todo mundo.
        con = owner_conn()
        with self.assertRaises(Exception) as e2:
            con.run("UPDATE free_periods SET ends_at = now() WHERE id = $1", pid)
        self.assertIn("não se altera", str(e2.exception))

    def test_removing_a_period_is_a_cancellation_with_a_reason_not_a_delete(self):
        cli = new_account("company")
        pid = scalar("SELECT id::text FROM free_periods WHERE org_id = $1", cli.org_id)
        with db_system() as c:
            from impacto.services import free_period as FP
            self.assertTrue(FP.cancel(c, period_id=pid, cancelled_by=None,
                                      reason="teste de cancelamento"))
        row = q1("SELECT status, cancel_reason, cancelled_at FROM free_periods WHERE id = $1", pid)
        self.assertEqual(row["status"], "cancelled")
        self.assertEqual(row["cancel_reason"], "teste de cancelamento")
        self.assertIsNotNone(row["cancelled_at"], "cancelamento sem carimbo de quando")
        # E o registro continua lá: é a prova de que a plataforma concedeu antes de tirar.
        self.assertEqual(scalar("SELECT count(*) FROM free_periods WHERE id = $1", pid), 1)

    def test_a_cancelled_period_does_not_come_back(self):
        cli = new_account("osc")
        pid = scalar("SELECT id::text FROM free_periods WHERE org_id = $1", cli.org_id)
        with db_system() as c:
            from impacto.services import free_period as FP
            FP.cancel(c, period_id=pid, cancelled_by=None, reason="teste")
        with self.assertRaises(Exception) as e:
            with db_system() as c:
                c.run("UPDATE free_periods SET status = 'active' WHERE id = $1", pid)
        self.assertIn("não volta a valer", str(e.exception))


class ExpiryIsNotPunishmentTests(unittest.TestCase):
    """O fim do período gratuito devolve a conta ao plano gratuito. Só isso."""

    def test_expiring_does_not_charge_suspend_or_delete(self):
        cli = new_account("osc")
        with db_system() as c:
            c.run("UPDATE organizations SET id = id WHERE id = $1", cli.org_id)  # no-op
        # Move o fim do período para o passado pelo caminho legítimo: cancela e concede um já vencido.
        with db_system() as c:
            from impacto.services import free_period as FP
            pid = c.scalar("SELECT id::text FROM free_periods WHERE org_id = $1", cli.org_id)
            FP.cancel(c, period_id=pid, cancelled_by=None, reason="reposicionando para o teste")
            c.run("INSERT INTO free_periods(org_id, source, reason, pricing_version, months,"
                  " started_at, ends_at, status) VALUES ($1,'PROMOTION','período já vencido para"
                  " exercitar a varredura','2026.00',1, now() - interval '40 days',"
                  " now() - interval '10 days','active')", cli.org_id)
            out = FP.sweep(c)
        self.assertGreaterEqual(out["expired"], 1)
        self.assertEqual(scalar("SELECT count(*) FROM platform_charges WHERE org_id = $1",
                                cli.org_id), 0, "a expiração gerou cobrança")
        self.assertEqual(scalar("SELECT status FROM organizations WHERE id = $1", cli.org_id),
                         "active", "a expiração suspendeu a organização")
        # E a conta continua respondendo: o plano gratuito é permanente.
        self.assertEqual(cli.get("/v1/commercial/state").status, 200)

    def test_the_account_is_told_that_nothing_was_charged(self):
        cli = new_account("company")
        with db_system() as c:
            from impacto.services import free_period as FP
            pid = c.scalar("SELECT id::text FROM free_periods WHERE org_id = $1", cli.org_id)
            FP.cancel(c, period_id=pid, cancelled_by=None, reason="reposicionando")
            c.run("INSERT INTO free_periods(org_id, source, reason, pricing_version, months,"
                  " started_at, ends_at, status) VALUES ($1,'PROMOTION','vencido','2026.00',1,"
                  " now() - interval '40 days', now() - interval '1 hour','active')", cli.org_id)
            FP.sweep(c)
        corpo = scalar("SELECT body FROM notifications WHERE org_id = $1"
                       " AND kind = 'billing.free_period_ended'", cli.org_id)
        self.assertIsNotNone(corpo, "o fim do período não avisou ninguém")
        self.assertIn("Nenhuma cobrança", corpo)
        self.assertIn("nenhum dado foi apagado", corpo.lower())


class NotificationWindowTests(unittest.TestCase):
    """90/60/30/7/1 dia, mais o lembrete semanal — cada um uma vez só."""

    def _conta_com_periodo(self, dias: int) -> Client:
        cli = new_account("osc")
        with db_system() as c:
            from impacto.services import free_period as FP
            pid = c.scalar("SELECT id::text FROM free_periods WHERE org_id = $1", cli.org_id)
            FP.cancel(c, period_id=pid, cancelled_by=None, reason="reposicionando para o teste")
            c.run("INSERT INTO free_periods(org_id, source, reason, pricing_version, months,"
                  " started_at, ends_at, status) VALUES ($1,'PROMOTION','janela de aviso',"
                  " '2026.00',1, now() - interval '1 day',"
                  # `dias` restantes é ceil(diferença/86400): faltando 13d23h, a pessoa lê "14
                  # dias". Para o cenário valer exatamente $2, o fim fica UMA HORA ABAIXO da
                  # fronteira — acima dela o ceil arredondaria para $2 + 1 e o teste mediria
                  # outra janela.
                  " now() + make_interval(days => $2) - interval '1 hour', 'active')",
                  cli.org_id, dias)
        return cli

    def test_each_window_notifies_exactly_once(self):
        for dias in (90, 60, 30, 7, 1):
            cli = self._conta_com_periodo(dias)
            with db_system() as c:
                from impacto.services import free_period as FP
                FP.notify_windows(c)
                FP.notify_windows(c)      # segunda passagem: não pode duplicar
            n = scalar("SELECT count(*) FROM notifications WHERE org_id = $1"
                       " AND kind = 'billing.free_period_ending'", cli.org_id)
            self.assertEqual(n, 1, f"janela de {dias} dias notificou {n} vezes")

    def test_the_warning_says_the_account_will_not_be_charged_without_authorization(self):
        cli = self._conta_com_periodo(30)
        with db_system() as c:
            from impacto.services import free_period as FP
            FP.notify_windows(c)
        corpo = scalar("SELECT body FROM notifications WHERE org_id = $1"
                       " AND kind = 'billing.free_period_ending'", cli.org_id)
        self.assertIn("NÃO será cobrado", corpo)
        self.assertIn("não existe assinatura", corpo)

    def test_a_day_that_is_not_a_window_says_nothing(self):
        cli = self._conta_com_periodo(45)      # 45 não é janela e não é múltiplo de 7 abaixo de 30
        with db_system() as c:
            from impacto.services import free_period as FP
            FP.notify_windows(c)
        self.assertEqual(scalar("SELECT count(*) FROM notifications WHERE org_id = $1"
                                " AND kind = 'billing.free_period_ending'", cli.org_id), 0)

    def test_the_weekly_reminder_runs_inside_the_last_thirty_days(self):
        cli = self._conta_com_periodo(14)      # múltiplo de 7, dentro de 30 dias
        with db_system() as c:
            from impacto.services import free_period as FP
            FP.notify_windows(c)
        self.assertEqual(scalar("SELECT count(*) FROM notifications WHERE org_id = $1"
                                " AND kind = 'billing.free_period_ending'", cli.org_id), 1)
