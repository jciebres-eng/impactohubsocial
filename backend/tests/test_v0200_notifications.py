"""v0.20.0 — motor de notificação: §22 (eventos mínimos) e §23 (não virar spam).

O DEFEITO CENTRAL QUE ESTES TESTES TRAVAM

Existiam três caminhos de notificação. Dois respeitavam a preferência da pessoa; o terceiro,
`app_notify`, não respeitava nenhuma — e era o caminho de 29 chamadas espalhadas pelo produto,
usando 15 prefixos que não correspondiam a grupo de preferência nenhum. Na prática: a pessoa
desligava todos os interruptores que a tela oferecia e continuava recebendo aviso de conformidade,
de candidatura, de pagamento, de evidência, de validação profissional e de situação institucional.

O interruptor existia. Não estava ligado a nada. Isso é pior que não ter interruptor, porque a
pessoa acredita ter escolhido.

O segundo defeito, igualmente invisível: `impacto/network/notify.py` AFIRMAVA no próprio docstring
que havia um teste chamado `test_todo_prefixo_de_evento_resolve_para_um_grupo_declarado`. Esse teste
não existia. Ele existe agora, abaixo, e é o que torna a afirmação verdadeira.
"""
from __future__ import annotations

import unittest

from impacto.network import events as EV
from impacto.network import notify as NT
from tests.support import db_system, new_account


def _kinds() -> dict[str, dict]:
    with db_system() as c:
        return {r["kind"]: r for r in c.query(
            "SELECT kind, grp, default_priority, emailable FROM notification_kinds")}


class CatalogInvariantTests(unittest.TestCase):
    """Nenhum aviso pode existir fora de um interruptor. Sem exceção."""

    def test_every_event_prefix_resolves_to_a_declared_group(self):
        """O teste que o docstring de notify.py dizia existir — e que não existia."""
        with db_system() as c:
            grupos = {r["grp"] for r in c.query(
                "SELECT DISTINCT grp FROM notification_kinds")}
        for evento in EV.EVENTS:
            grp = NT._grp(evento)
            self.assertIn(grp, grupos,
                          f"o evento {evento} resolve para o grupo '{grp}', que não existe no "
                          "catálogo: silenciar esse grupo não silenciaria nada")

    def test_every_notification_kind_used_in_the_code_is_in_the_catalog(self):
        """Varre as chamadas reais de `app_notify` e exige catálogo para cada prefixo."""
        import pathlib
        import re
        pkg = pathlib.Path(__file__).resolve().parents[1] / "impacto"
        catalogo = set(_kinds())
        faltando = set()
        for f in pkg.rglob("*.py"):
            for m in re.finditer(r"app_notify\([^)]*?'([a-z_]+)(?:\.[a-z_]+)?'", f.read_text(encoding="utf-8")):
                if m.group(1) not in catalogo:
                    faltando.add(f"{m.group(1)} ({f.name})")
        self.assertEqual(faltando, set(),
                         "tipo de aviso sem grupo de preferência declarado: a pessoa não consegue "
                         "silenciá-lo")

    def test_the_fifteen_legacy_kinds_now_belong_to_a_switch(self):
        cat = _kinds()
        for legado in ("compliance", "application", "payment", "alert", "execution", "evidence",
                       "professional", "agreement", "mentoring", "solution", "impact", "interest",
                       "review", "qualification", "institutional"):
            self.assertIn(legado, cat, f"{legado} continua fora de qualquer interruptor")

    def test_security_alerts_are_critical_by_catalog_not_by_patch(self):
        self.assertEqual(_kinds()["security"]["default_priority"], "critical")
        self.assertTrue(_kinds()["security"]["emailable"])


class PreferenceIsHonouredTests(unittest.TestCase):
    """O interruptor desliga de verdade — inclusive no caminho que o ignorava."""

    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")

    def _avisos(self, kind_prefix: str) -> int:
        with db_system() as c:
            return c.scalar("SELECT count(*) FROM notifications WHERE user_id = $1"
                            " AND split_part(kind, '.', 1) = $2", self.c.user["id"], kind_prefix)

    def test_1_app_notify_respects_a_silenced_group(self):
        antes = self._avisos("compliance")
        with db_system() as c:
            c.run("INSERT INTO notification_prefs(user_id, grp, in_app, email)"
                  " VALUES ($1,'account',false,false) ON CONFLICT (user_id, grp)"
                  " DO UPDATE SET in_app = false, email = false", self.c.user["id"])
            c.scalar("SELECT app_notify($1,$2,'compliance','Teste','Corpo','/x')",
                     self.c.org_id, self.c.user["id"])
        self.assertEqual(self._avisos("compliance"), antes,
                         "`compliance` pertence ao grupo `account`; com `account` desligado o aviso "
                         "NÃO pode ser gravado")

    def test_2_the_same_call_lands_when_the_group_is_on(self):
        with db_system() as c:
            c.run("UPDATE notification_prefs SET in_app = true WHERE user_id = $1 AND grp = 'account'",
                  self.c.user["id"])
            c.scalar("SELECT app_notify($1,$2,'compliance','Teste ligado','Corpo','/x')",
                     self.c.org_id, self.c.user["id"])
            row = c.one("SELECT grp, priority FROM notifications WHERE user_id = $1"
                        " AND title = 'Teste ligado'", self.c.user["id"])
        self.assertIsNotNone(row, "com o grupo ligado o aviso tem de chegar")
        self.assertEqual(row["grp"], "account", "o grupo é resolvido no INSERT, não na leitura")
        self.assertEqual(row["priority"], "high", "prioridade padrão vem do catálogo")

    def test_3_an_unmapped_kind_is_never_lost_but_is_counted(self):
        with db_system() as c:
            c.scalar("SELECT app_notify($1,$2,'tipo_inexistente','Sem catálogo','Corpo','/x')",
                     self.c.org_id, self.c.user["id"])
            row = c.one("SELECT grp, unmapped_kind FROM notifications"
                        " WHERE title = 'Sem catálogo' AND user_id = $1", self.c.user["id"])
        self.assertIsNotNone(row, "aviso NUNCA é descartado por falta de declaração")
        self.assertTrue(row["unmapped_kind"], "mas a lacuna fica contada, não silenciosa")


class NoSpamTests(unittest.TestCase):
    """§23: prioridade, quiet period, rate limit e agrupamento — com o crítico sempre passando."""

    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")

    def test_1_the_platform_policy_is_declared_in_one_readable_place(self):
        with db_system() as c:
            pol = c.one("SELECT max_per_day, quiet_from::text AS quiet_from,"
                        " quiet_to::text AS quiet_to, retry_max, note FROM notification_policy")
        self.assertGreaterEqual(pol["max_per_day"], 1)
        self.assertIsNotNone(pol["quiet_from"])
        self.assertIn("CRÍTICA", pol["note"], "a exceção do crítico tem de estar escrita")

    def test_2_the_quiet_period_holds_the_notification_instead_of_dropping_it(self):
        with db_system() as c:
            c.run("INSERT INTO notification_prefs(user_id, grp, in_app, email, quiet_from, quiet_to)"
                  " VALUES ($1,'network',true,true,'00:00','23:59')"
                  " ON CONFLICT (user_id, grp) DO UPDATE SET quiet_from = '00:00', quiet_to = '23:59'",
                  self.c.user["id"])
            c.scalar("SELECT app_notify($1,$2,'network.notice','Silenciado','Corpo','/x')",
                     self.c.org_id, self.c.user["id"])
            row = c.one("SELECT deliver_after > now() AS retido FROM notifications"
                        " WHERE title = 'Silenciado' AND user_id = $1", self.c.user["id"])
        self.assertIsNotNone(row, "janela de silêncio RETÉM; descartar seria perder o fato")
        self.assertTrue(row["retido"], "a entrega externa fica para depois da janela")

    def test_3_a_critical_notification_ignores_the_quiet_period(self):
        with db_system() as c:
            c.scalar("SELECT app_notify($1,$2,'security','Sessões encerradas','Corpo','/x')",
                     self.c.org_id, self.c.user["id"])
            row = c.one("SELECT priority, deliver_after <= now() AS entrega_agora"
                        " FROM notifications WHERE title = 'Sessões encerradas' AND user_id = $1",
                        self.c.user["id"])
        self.assertEqual(row["priority"], "critical")
        self.assertTrue(row["entrega_agora"],
                        "avisar amanhã de manhã que uma credencial pode ter sido copiada não é avisar")

    def test_4_the_rate_limit_throttles_instead_of_discarding(self):
        c2 = new_account("osc")
        with db_system() as c:
            c.run("INSERT INTO notification_prefs(user_id, grp, in_app, email, max_per_day)"
                  " VALUES ($1,'network',true,true,3) ON CONFLICT (user_id, grp)"
                  " DO UPDATE SET max_per_day = 3", c2.user["id"])
            for i in range(6):
                c.scalar("SELECT app_notify($1,$2,'network.notice',$3,'Corpo','/x')",
                         c2.org_id, c2.user["id"], f"Aviso {i}")
            total = c.scalar("SELECT count(*) FROM notifications WHERE user_id = $1"
                             " AND grp = 'network'", c2.user["id"])
            retidos = c.scalar("SELECT count(*) FROM notifications WHERE user_id = $1"
                               " AND grp = 'network' AND throttled", c2.user["id"])
        self.assertEqual(total, 6, "nenhum aviso é descartado pelo limite")
        self.assertEqual(retidos, 3, "os que passaram do teto ficam retidos para o agrupamento")

    def test_5_the_daily_digest_holds_delivery_for_the_declared_hour(self):
        c3 = new_account("osc")
        with db_system() as c:
            c.run("INSERT INTO notification_prefs(user_id, grp, in_app, email, digest)"
                  " VALUES ($1,'message',true,true,'daily') ON CONFLICT (user_id, grp)"
                  " DO UPDATE SET digest = 'daily'", c3.user["id"])
            c.scalar("SELECT app_notify($1,$2,'message.notice','Agrupado','Corpo','/x')",
                     c3.org_id, c3.user["id"])
            row = c.one("SELECT deliver_after > now() AS retido FROM notifications"
                        " WHERE title = 'Agrupado' AND user_id = $1", c3.user["id"])
        self.assertTrue(row["retido"])


class DeliveryStatusTests(unittest.TestCase):
    """§23: retry e delivery status. `sent` significa aceito pelo servidor — nada além disso."""

    def test_the_delivery_table_cannot_claim_the_message_was_read(self):
        with db_system() as c:
            estados = c.scalar(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                " WHERE conname = 'notification_deliveries_status_check'")
        for proibido in ("delivered", "read", "opened"):
            self.assertNotIn(f"'{proibido}'", estados,
                             "a plataforma não tem como saber se o e-mail chegou ou foi lido")
        for exigido in ("pending", "sent", "failed", "skipped", "given_up"):
            self.assertIn(f"'{exigido}'", estados)

    def test_a_skip_records_why_instead_of_leaving_support_to_guess(self):
        with db_system() as c:
            motivos = c.scalar(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                " WHERE conname = 'notification_deliveries_skipped_reason_check'")
        for motivo in ("preference", "quiet_period", "rate_limit", "no_verified_email"):
            self.assertIn(f"'{motivo}'", motivos)

    def test_the_email_job_reports_what_it_can_and_cannot_know(self):
        from impacto.services import hub
        self.assertIn("ACEITOS pelo servidor", hub.notification_emails.__doc__ or "",
                      msg="o docstring tem de dizer o que `sent` significa")



class ScheduledWorkTests(unittest.TestCase):
    """Três funções existiam, eram testáveis e NUNCA eram executadas por ninguém."""

    def test_the_three_orphan_functions_are_now_registered_jobs(self):
        from impacto import jobs
        registrados = {nome for nome, _ in jobs.JOBS}
        for esperado in ("proposal_expiry", "listing_expiry", "seal_recheck", "deadline_sweep"):
            self.assertIn(esperado, registrados)

    def test_a_proposal_past_its_deadline_actually_expires_and_notifies(self):
        from impacto.network import proposals as PROP
        emissor = new_account("company")
        receptor = new_account("osc")
        with db_system() as c:
            pid = c.scalar(
                "INSERT INTO proposals(kind, sender_org_id, receiver_org_id, title, purpose, terms,"
                " status, sent_at, expires_at, created_by)"
                " VALUES ('partnership',$1,$2,'Proposta vencida',"
                " 'Objetivo declarado para o teste de expiração automática.',"
                " 'Termos declarados para o teste de expiração automática.',"
                " 'sent', now() - interval '10 days', now() - interval '1 day', $3)"
                " RETURNING id::text", emissor.org_id, receptor.org_id, emissor.user["id"])
            out = PROP.expire_due(c)
            estado = c.scalar("SELECT status FROM proposals WHERE id = $1", pid)
            evento = c.scalar("SELECT count(*) FROM domain_events WHERE event = 'Proposal.expired'"
                              " AND subject_id = $1", pid)
        self.assertGreaterEqual(out["expired"], 1)
        self.assertEqual(estado, "expired",
                         "sem chamador, a proposta ficava em 'sent' para sempre")
        self.assertEqual(evento, 1, "e o evento que notifica nunca acontecia")

    def test_the_seal_recheck_is_reachable(self):
        from impacto.impact import seals
        with db_system() as c:
            out = seals.recheck(c)
        self.assertIn("checked", out)
        self.assertIn("revoked", out)


class MinimumEventsTests(unittest.TestCase):
    """§22: os eventos mínimos — e a declaração honesta dos que NÃO existem."""

    def test_no_declared_domain_event_is_a_promise_the_code_does_not_keep(self):
        """Evento declarado e nunca emitido é a mesma mentira do importador que não existia."""
        import pathlib
        import re
        pkg = pathlib.Path(__file__).resolve().parents[1] / "impacto"
        fontes = "\n".join(f.read_text(encoding="utf-8") for f in pkg.rglob("*.py")
                           if f.name != "events.py")
        nunca = [e for e in EV.EVENTS if not re.search(rf'"{re.escape(e)}"', fontes)]
        self.assertEqual(
            nunca, [],
            "estes eventos estão declarados em network/events.py e nenhum código os emite: "
            "ou o fato passa a gerar o evento, ou o evento sai do catálogo")

    def test_the_impact_layer_notifies_now(self):
        """Selo, reputação e afirmação não avisavam ninguém sobre nada."""
        import pathlib
        impact = pathlib.Path(__file__).resolve().parents[1] / "impacto" / "impact"
        fontes = "\n".join(f.read_text(encoding="utf-8") for f in impact.rglob("*.py"))
        for evento in ("Seal.awarded", "Seal.revoked", "Reputation.band_changed",
                       "Claim.review_requested"):
            self.assertIn(evento, fontes, f"{evento} não é emitido pela camada de impacto")

    def test_deadlines_that_the_platform_knew_about_are_swept(self):
        from impacto.ops import deadlines
        self.assertEqual(deadlines.WINDOWS, (30, 7, 1))
        with db_system() as c:
            out = deadlines.sweep(c)
        for chave in ("milestones", "calls", "proposals", "seals", "agreement_milestones"):
            self.assertIn(chave, out, f"{chave} não é varrido")


class ApiSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")

    def test_the_catalog_route_answers_which_notifications_exist(self):
        r = self.c.get("/v1/notifications/catalog")
        self.assertEqual(r.status, 200, r)
        self.assertGreaterEqual(len(r.json["items"]), 30)
        self.assertIn("não pertenciam a interruptor nenhum", r.json["note"])
        self.assertIsNotNone(r.json["policy"]["max_per_day"])

    def test_the_inbox_exposes_priority_and_what_to_do(self):
        with db_system() as c:
            c.scalar("SELECT app_notify($1,$2,'compliance','Com prioridade','Corpo','/x')",
                     self.c.org_id, self.c.user["id"])
        r = self.c.get("/v1/notifications")
        self.assertEqual(r.status, 200, r)
        linha = next(i for i in r.json["items"] if i["title"] == "Com prioridade")
        self.assertEqual(linha["priority"], "high")
        self.assertEqual(linha["grp"], "account")
        self.assertEqual(linha["kind_label"], "Conformidade")

    def test_preferences_say_what_each_switch_actually_turns_off(self):
        r = self.c.get("/v1/notifications/prefs")
        self.assertEqual(r.status, 200, r)
        conta = next(i for i in r.json["items"] if i["grp"] == "account")
        rotulos = {k["kind"] for k in conta["kinds"]}
        self.assertIn("compliance", rotulos)
        self.assertIn("security", rotulos)
        self.assertIn("digest", conta)

    def test_a_person_can_set_quiet_hours_through_the_api(self):
        r = self.c.put("/v1/notifications/prefs", {"items": [
            {"grp": "project", "in_app": True, "email": False,
             "quiet_from": "23:00", "quiet_to": "06:30", "max_per_day": 20, "digest": "daily"}]})
        self.assertEqual(r.status, 200, r)
        projeto = next(i for i in r.json["items"] if i["grp"] == "project")
        self.assertEqual(projeto["quiet_from"], "23:00:00")
        self.assertEqual(projeto["max_per_day"], 20)
        self.assertEqual(projeto["digest"], "daily")
