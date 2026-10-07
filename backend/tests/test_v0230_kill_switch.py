"""Interruptor de emergência: para a plataforma sem cegar a auditoria e sem se trancar fora.

Um interruptor de emergência é fácil de implementar e fácil de implementar ERRADO. As três formas
de errar, e o teste que fecha cada uma:

1. **Bloquear a auditoria.** Durante um incidente, registrar o que está acontecendo é a única coisa
   que não se pode perder. `TheAuditTrailIsNeverBlockedTests`.
2. **Trancar-se do lado de fora.** Se a rota que libera o interruptor for bloqueada por ele, o
   incidente vira indisponibilidade permanente. `TheBreakGlassPathStaysOpenTests`.
3. **Trancar a equipe que responde.** Bloquear login de todos inclui quem precisa entrar para
   investigar. `TheTeamCanStillGetInTests`.

E a forma de errar que não é de desenho, mas de disciplina: deixar existir um caminho que liga o
interruptor sem registrar o evento. `OnlyTheTriggerWritesTheStateTests`.
"""
from __future__ import annotations

import unittest

from tests.support import PASSWORD, Client, app_tx, db_system, make_admin, make_staff, new_account


def _liberar_tudo():
    """Rede de segurança: nenhum teste deixa a plataforma parada para os seguintes.

    Escreve pelo histórico, como o produto faz — não por UPDATE direto no estado. Se o gatilho
    parar de funcionar, a limpeza falha e os testes seguintes acusam, em vez de esconder.
    """
    with db_system() as c:
        for escopo in ("mutations", "logins", "uploads", "integrations", "maintenance"):
            if c.scalar("SELECT engaged FROM kill_switch_state WHERE scope = $1", escopo):
                c.run("INSERT INTO kill_switch_events(scope, action, reason) VALUES ($1,'release',$2)",
                      escopo, "limpeza automatica de teste")
    # Sem isto, o cache de processo mantém "parado" por até 5 segundos e o teste SEGUINTE herda uma
    # plataforma desligada. A primeira execução desta suíte fez exatamente isso.
    from impacto.core import killswitch
    killswitch.invalidate()


def _acionar(escopo: str, motivo: str = "incidente simulado em teste automatizado"):
    with db_system() as c:
        c.run("INSERT INTO kill_switch_events(scope, action, reason) VALUES ($1,'engage',$2)", escopo, motivo)
    from impacto.core import killswitch
    killswitch.invalidate()


def _soltar(escopo: str):
    with db_system() as c:
        c.run("INSERT INTO kill_switch_events(scope, action, reason) VALUES ($1,'release',$2)",
              escopo, "fim do incidente simulado em teste")
    from impacto.core import killswitch
    killswitch.invalidate()


class TheSwitchActuallyStopsWritesTests(unittest.TestCase):
    """O básico: ligado, a escrita para; a leitura não."""

    def setUp(self):
        _liberar_tudo()
        self.addCleanup(_liberar_tudo)

    def test_read_only_mode_refuses_writes_and_allows_reads(self):
        c = new_account()
        antes = c.get("/v1/me")
        self.assertEqual(200, antes.status)
        _acionar("mutations")
        escrita = c.post("/v1/projects", {"name": "Projeto durante incidente", "summary": "x" * 40})
        self.assertEqual(503, escrita.status, "modo somente leitura não recusou a escrita")
        self.assertEqual("platform_halted", escrita.json["code"])
        self.assertEqual("mutations", escrita.json["details"]["scope"])
        leitura = c.get("/v1/me")
        self.assertEqual(200, leitura.status, "modo somente leitura não deveria bloquear consulta")

    def test_the_incident_reason_never_reaches_the_blocked_user(self):
        """Dizer "banco comprometido" a quem está do lado de fora é entregar reconhecimento."""
        c = new_account()
        _acionar("mutations", "banco de dados possivelmente comprometido, segredo X vazado")
        r = c.post("/v1/projects", {"name": "x", "summary": "y" * 40})
        corpo = r.body.decode("utf-8")
        self.assertNotIn("comprometido", corpo)
        self.assertNotIn("vazado", corpo)

    def test_maintenance_mode_refuses_reads_too(self):
        c = new_account()
        _acionar("maintenance")
        r = c.get("/v1/me")
        self.assertEqual(503, r.status, "manutenção total deveria recusar até leitura")
        self.assertEqual("maintenance", r.json["details"]["scope"])

    def test_upload_scope_blocks_only_uploads(self):
        c = new_account()
        _acionar("uploads")
        comum = c.post("/v1/projects", {"name": "Projeto com upload suspenso", "summary": "z" * 40})
        self.assertNotEqual(503, comum.status,
                            "suspender upload não deveria suspender o resto da plataforma")

    def test_releasing_brings_the_platform_back(self):
        c = new_account()
        _acionar("mutations")
        self.assertEqual(503, c.post("/v1/projects", {"name": "a", "summary": "b" * 40}).status)
        _soltar("mutations")
        r = c.post("/v1/projects", {"name": "Projeto depois do incidente", "summary": "c" * 40})
        self.assertNotEqual(503, r.status, "liberar o interruptor não devolveu a escrita")


class TheAuditTrailIsNeverBlockedTests(unittest.TestCase):
    """A regra que define o desenho: o interruptor nunca cega quem investiga."""

    def setUp(self):
        _liberar_tudo()
        self.addCleanup(_liberar_tudo)

    def test_audit_reading_works_under_full_maintenance(self):
        c, _ = make_admin()
        _acionar("maintenance")
        r = c.get("/v1/admin/audit")
        self.assertEqual(200, r.status,
                         "a trilha de auditoria ficou inacessível justamente durante o incidente")

    def test_audit_writing_still_happens_under_read_only(self):
        """Escrita de auditoria não é "escrita" para efeito do interruptor.

        Prova de ponta a ponta: com `mutations` ligado, um login falho — que a plataforma recusa de
        qualquer forma — tem de continuar gerando o evento na trilha.
        """
        c = new_account()
        _acionar("mutations")
        with db_system() as conn:
            antes = conn.scalar("SELECT count(*) FROM audit_events WHERE action = 'auth.login_failed'")
        r = Client().post("/v1/auth/login", {"email": c.email, "password": "errada_de_proposito"})
        self.assertEqual(401, r.status)
        with db_system() as conn:
            depois = conn.scalar("SELECT count(*) FROM audit_events WHERE action = 'auth.login_failed'")
        self.assertGreater(depois, antes,
                           "a trilha parou de registrar enquanto o interruptor estava acionado")

    def test_the_privileged_access_trail_also_stays_readable(self):
        c, _ = make_admin()
        _acionar("maintenance")
        self.assertEqual(200, c.get("/v1/admin/privileged-access").status)

    def test_every_exemption_has_a_reason(self):
        """Isenção sem motivo escrito é um buraco que ninguém lembra de ter aberto."""
        from impacto.core.killswitch import EXEMPT_PREFIXES
        curtos = {p: r for p, r in EXEMPT_PREFIXES.items() if len(r) < 40}
        self.assertEqual({}, curtos, f"isenções sem motivo de verdade: {list(curtos)}")

    def test_the_audit_routes_are_in_the_exemption_list_by_prefix_not_by_luck(self):
        from impacto.core.killswitch import is_exempt
        for caminho in ("/v1/admin/audit", "/v1/admin/audit/export", "/v1/admin/privileged-access"):
            with self.subTest(caminho=caminho):
                self.assertTrue(is_exempt(caminho))

    def test_the_exemption_list_does_not_accidentally_exempt_writing_routes(self):
        """A isenção é para investigar, não para escapar. Nenhum prefixo isento cobre rota de produto."""
        from impacto.core.killswitch import is_exempt
        for caminho in ("/v1/projects", "/v1/documents", "/v1/organizations", "/v1/applications",
                        "/v1/indicators", "/v1/billing/quote"):
            with self.subTest(caminho=caminho):
                self.assertFalse(is_exempt(caminho), f"{caminho} escapa do interruptor")


class TheBreakGlassPathStaysOpenTests(unittest.TestCase):
    """O interruptor não pode se trancar do lado de fora."""

    def setUp(self):
        _liberar_tudo()
        self.addCleanup(_liberar_tudo)

    def test_the_switch_can_be_released_while_fully_engaged(self):
        c, segredo = make_admin()
        _acionar("maintenance")
        _acionar("mutations")
        r = c.post("/v1/admin/kill-switch",
                   {"scope": "maintenance", "action": "release",
                    "reason": "liberacao durante teste de vidro quebrado"})
        self.assertEqual(200, r.status,
                         "a rota que libera o interruptor foi bloqueada pelo próprio interruptor")
        self.assertFalse(r.json["engaged"])

    def test_reading_the_switch_state_works_while_fully_engaged(self):
        c, _ = make_admin()
        _acionar("maintenance")
        r = c.get("/v1/admin/kill-switch")
        self.assertEqual(200, r.status)
        self.assertTrue(any(s["scope"] == "maintenance" and s["engaged"] for s in r.json["scopes"]))

    def test_the_public_status_route_answers_while_engaged(self):
        """Sem isto a aplicação não tem como exibir aviso: só erro sem explicação."""
        _acionar("mutations")
        r = Client().get("/v1/meta/platform-status")
        self.assertEqual(200, r.status)
        self.assertFalse(r.json["operating"])
        self.assertIn("mutations", r.json["halted"])

    def test_the_public_status_route_does_not_leak_the_reason(self):
        _acionar("mutations", "credencial de provedor exposta no repositorio publico")
        corpo = Client().get("/v1/meta/platform-status").body.decode("utf-8")
        self.assertNotIn("credencial", corpo)
        self.assertNotIn("repositorio", corpo)

    def test_logout_works_while_engaged(self):
        """Encerrar sessão REDUZ exposição. Bloquear a saída é o contrário do objetivo."""
        c = new_account()
        _acionar("maintenance")
        r = c.post("/v1/auth/logout", {})
        self.assertNotEqual(503, r.status, "a saída foi bloqueada durante o incidente")


class TheTeamCanStillGetInTests(unittest.TestCase):
    """O escopo `logins` bloqueia o público, não quem responde ao incidente."""

    def setUp(self):
        _liberar_tudo()
        self.addCleanup(_liberar_tudo)

    def test_a_client_cannot_log_in_while_logins_are_halted(self):
        c = new_account()
        _acionar("logins")
        r = Client().post("/v1/auth/login", {"email": c.email, "password": PASSWORD})
        self.assertEqual(503, r.status, f"login de cliente passou durante bloqueio: {r.json}")
        self.assertEqual("logins", r.json["details"]["scope"])

    def test_internal_staff_can_still_log_in_while_logins_are_halted(self):
        equipe = make_staff("support")
        _acionar("logins")
        r = Client().post("/v1/auth/login", {"email": equipe.email, "password": PASSWORD})
        self.assertNotEqual(503, r.status,
                            "a equipe que responde ao incidente foi trancada do lado de fora")

    def test_an_open_session_survives_the_login_block(self):
        """Bloquear login não é derrubar quem está dentro — isso seria outra decisão, mais grave."""
        c = new_account()
        _acionar("logins")
        self.assertEqual(200, c.get("/v1/me").status)

    def test_the_block_lives_at_session_issuance_not_at_one_route(self):
        """Senha, MFA, OIDC e convite emitem sessão por caminhos diferentes; a trava é uma só."""
        fonte = (__import__("pathlib").Path(__file__).parent.parent / "impacto" / "services" / "auth.py").read_text(encoding="utf-8")
        corpo = fonte[fonte.index("def issue_session"):]
        corpo = corpo[:corpo.index("\ndef ")]
        self.assertIn('_halt_engaged(ctx, "logins")', corpo,
                      "a trava não está dentro de issue_session: um dos caminhos de emissão "
                      "(senha, MFA, OIDC, convite) vai ficar para trás")
        self.assertIn('_halt_engaged(ctx, "maintenance")', corpo,
                      "manutenção total tem de valer na porta de entrada também")
        # E não há nenhuma outra trava de login espalhada por rota, que é como esta regra se perde.
        fora = fonte.replace(corpo, "")
        self.assertNotIn('_halt_engaged(ctx, "logins")', fora)


class OnlyTheTriggerWritesTheStateTests(unittest.TestCase):
    """Não existe caminho para parar a plataforma sem deixar o evento no histórico."""

    def setUp(self):
        _liberar_tudo()
        self.addCleanup(_liberar_tudo)

    def test_the_history_is_append_only_even_for_the_database_owner(self):
        """Pelo contexto da aplicação isto daria "permission denied" — e o teste passaria sem provar nada.

        A lição é a do teste de deriva de chave estrangeira da v0.22.0: ele passava por erro de
        privilégio, não pela trava que dizia conferir. Aqui a tentativa é feita como DONO do banco,
        que tem todos os privilégios, para que o que recuse seja o gatilho.
        """
        from tests.support import owner_conn
        _acionar("mutations")
        conn = owner_conn()
        try:
            ident = conn.scalar("SELECT id FROM kill_switch_events ORDER BY id DESC LIMIT 1")
            with self.assertRaises(Exception) as erro:
                conn.run("UPDATE kill_switch_events SET reason = 'reescrito' WHERE id = $1", ident)
            self.assertIn("append-only", str(erro.exception))
        finally:
            conn.close()

    def test_the_history_cannot_be_deleted_even_by_the_database_owner(self):
        from tests.support import owner_conn
        _acionar("mutations")
        conn = owner_conn()
        try:
            ident = conn.scalar("SELECT id FROM kill_switch_events ORDER BY id DESC LIMIT 1")
            with self.assertRaises(Exception) as erro:
                conn.run("DELETE FROM kill_switch_events WHERE id = $1", ident)
            self.assertIn("append-only", str(erro.exception))
        finally:
            conn.close()

    def test_the_application_cannot_write_the_state_table_at_all(self):
        """O estado só é escrito pelo gatilho. Sem isto, haveria caminho para parar sem registrar."""
        _acionar("mutations")
        with db_system() as c:
            with self.assertRaises(Exception) as erro:
                c.run("UPDATE kill_switch_state SET engaged = false WHERE scope = 'mutations'")
            self.assertIn("denied", str(erro.exception).lower())

    def test_a_reason_shorter_than_ten_characters_is_refused_by_the_database(self):
        """A trava existe no schema E no banco. Esta prova é a do banco, e usa SAVEPOINT.

        Capturar a exceção sem SAVEPOINT abortaria a transação e tudo depois dela falharia por um
        motivo que não é o do teste.
        """
        with db_system() as c:
            c.run("SAVEPOINT s")
            with self.assertRaises(Exception) as erro:
                c.run("INSERT INTO kill_switch_events(scope, action, reason) VALUES ('mutations','engage','teste')")
            c.run("ROLLBACK TO SAVEPOINT s")
            self.assertIn("reason", str(erro.exception))

    def test_engaged_without_reason_is_an_impossible_state(self):
        """Ligado sem motivo e sem horário: quem investiga depois precisa dos dois."""
        from tests.support import owner_conn
        conn = owner_conn()
        try:
            with self.assertRaises(Exception) as erro:
                conn.run("UPDATE kill_switch_state SET engaged = true, reason = NULL, since = NULL"
                         " WHERE scope = 'mutations'")
            self.assertIn("kill_switch_engaged_is_justified", str(erro.exception))
        finally:
            conn.close()

    def test_the_state_is_derived_and_every_engage_left_a_trace(self):
        """Estado ligado sem evento correspondente significaria que existe um caminho escondido."""
        _acionar("mutations")
        with db_system() as c:
            for linha in c.query("SELECT scope FROM kill_switch_state WHERE engaged"):
                ultimo = c.scalar("SELECT action FROM kill_switch_events WHERE scope = $1"
                                  " ORDER BY id DESC LIMIT 1", linha["scope"])
                self.assertEqual("engage", ultimo,
                                 f"escopo {linha['scope']} está ligado sem evento de acionamento")

    def test_an_organization_session_cannot_read_the_incident_history(self):
        """O motivo do incidente é informação de operação; RLS, não só rota."""
        c = new_account()
        with app_tx(c) as conn:
            self.assertEqual(0, conn.scalar("SELECT count(*) FROM kill_switch_events"))

    def test_an_organization_session_can_read_the_state_but_not_the_reason_through_the_api(self):
        _acionar("mutations", "motivo que nao pode vazar para cliente nenhum")
        c = new_account()
        r = c.get("/v1/meta/platform-status")
        self.assertEqual(200, r.status)
        self.assertNotIn("vazar", r.body.decode("utf-8"))


class OnlyTheHighestRoleCanStopThePlatformTests(unittest.TestCase):

    def setUp(self):
        _liberar_tudo()
        self.addCleanup(_liberar_tudo)

    def test_a_client_cannot_reach_the_switch(self):
        c = new_account()
        self.assertIn(c.get("/v1/admin/kill-switch").status, (401, 403))

    def test_a_staff_role_without_the_permission_cannot_engage_it(self):
        c = make_staff("support")
        r = c.post("/v1/admin/kill-switch",
                   {"scope": "mutations", "action": "engage", "reason": "tentativa indevida de parada"})
        self.assertEqual(403, r.status)

    def test_the_permission_is_super_admin_only_in_the_catalog(self):
        with db_system() as c:
            linha = c.one("SELECT super_admin_only, only_reason FROM permission_catalog"
                          " WHERE permission = 'security.kill_switch'")
        self.assertIsNotNone(linha, "a permissão não está no catálogo")
        self.assertTrue(linha["super_admin_only"])
        self.assertGreaterEqual(len(linha["only_reason"] or ""), 60,
                                "permissão exclusiva de super-administrador exige motivo escrito")

    def test_the_permission_demands_re_authentication(self):
        from impacto.core.access import STEP_UP_PERMISSIONS
        self.assertIn("security.kill_switch", STEP_UP_PERMISSIONS,
                      "parar a plataforma sem confirmar identidade é negação de serviço com a "
                      "credencial da própria vítima")

    def test_engaging_without_step_up_is_refused(self):
        c, _ = make_admin()
        # `make_admin` já reautentica; aqui expira a janela de propósito.
        with db_system() as conn:
            conn.run("UPDATE sessions SET reauth_at = now() - interval '1 day'"
                     " WHERE user_id = (SELECT id FROM users WHERE email = $1)", c.email)
        r = c.post("/v1/admin/kill-switch",
                   {"scope": "mutations", "action": "engage", "reason": "parada sem reautenticacao"})
        self.assertEqual(401, r.status, f"parou a plataforma sem reautenticar: {r.json}")
        self.assertEqual("step_up_required", r.json["code"])
        self.assertTrue(r.json["details"]["step_up_required"])
        # E a plataforma continua de pé: a recusa não deixou estado pela metade.
        with db_system() as conn:
            self.assertFalse(conn.scalar("SELECT engaged FROM kill_switch_state WHERE scope = 'mutations'"))


class TheSwitchLeavesAnAuditTrailOfItsOwnTests(unittest.TestCase):

    def setUp(self):
        _liberar_tudo()
        self.addCleanup(_liberar_tudo)

    def test_engaging_through_the_api_writes_an_audit_event(self):
        c, _ = make_admin()
        r = c.post("/v1/admin/kill-switch",
                   {"scope": "integrations", "action": "engage",
                    "reason": "integracao despejando dado errado em producao"})
        self.assertEqual(200, r.status, r.json)
        with db_system() as conn:
            acao = conn.scalar("SELECT action FROM audit_events WHERE object_type = 'kill_switch'"
                               "   AND object_id = 'integrations' ORDER BY seq DESC LIMIT 1")
        self.assertEqual("security.kill_switch_engaged", acao)

    def test_the_audit_action_is_a_declared_security_action(self):
        from impacto.services.audit import SECURITY_ACTIONS
        self.assertIn("security.kill_switch_engaged", SECURITY_ACTIONS)
        self.assertIn("security.kill_switch_released", SECURITY_ACTIONS)

    def test_the_block_is_counted_so_the_alert_can_see_it(self):
        c = new_account()
        _acionar("mutations")
        c.post("/v1/projects", {"name": "x", "summary": "y" * 40})
        corpo = Client().get("/metrics").body.decode("utf-8")
        self.assertIn("impacto_kill_switch_blocked_total", corpo)


if __name__ == "__main__":
    unittest.main()
