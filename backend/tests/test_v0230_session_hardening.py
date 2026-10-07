"""A sessão passa a vencer: idade máxima da família e inatividade.

O DEFEITO, ENCONTRADO POR AUDITORIA

`issue_session()` gravava `refresh_expires_at = now() + 30 dias` em TODA rotação, inclusive nas
rotações da MESMA família. Trinta dias contados sempre do último uso **nunca vencem para quem está
usando**: um refresh token roubado e renovado dentro da janela sobrevivia indefinidamente. Só senha
trocada, reset, logout global ou detecção de reuso o encerravam.

E `sessions.last_seen_at` era escrito a cada minuto e **nunca lido** para expirar nada — uma sessão
esquecida em máquina compartilhada valia trinta dias.

Os dois prazos são conferidos em DOIS lugares de propósito: na renovação, porque é ali que a sessão
pede mais tempo; e no caminho do token de acesso, porque conferir só na renovação deixaria a sessão
vencida respondendo por até quinze minutos a mais — e, pior, uma sessão usada a cada quatorze
minutos nunca passaria pela renovação.
"""
from __future__ import annotations

import unittest

from tests.support import db_system, new_account, server


def _envelhecer_familia(user_id: str, segundos: int) -> None:
    """Empurra o nascimento da família para o passado, como o tempo faria."""
    with db_system() as c:
        c.run("UPDATE sessions SET family_started_at = now() - make_interval(secs => $2)"
              " WHERE user_id = $1", user_id, segundos)


def _tornar_inativa(user_id: str, segundos: int) -> None:
    with db_system() as c:
        c.run("UPDATE sessions SET last_seen_at = now() - make_interval(secs => $2)"
              " WHERE user_id = $1", user_id, segundos)


class TheSessionFamilyHasAMaximumAgeTests(unittest.TestCase):

    def test_the_family_birth_is_carried_across_rotations(self):
        """É a propagação que faz a idade vencer. Sem ela, cada rotação zeraria o relógio."""
        c = new_account("osc")
        with db_system() as d:
            antes = d.one("SELECT family_id::text AS fid, family_started_at FROM sessions"
                          " WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1", c.user["id"])
        self.assertEqual(c.post("/v1/auth/refresh", {"refresh_token": c.refresh_token}).status, 200)
        with db_system() as d:
            depois = d.one("SELECT family_id::text AS fid, family_started_at FROM sessions"
                           " WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1", c.user["id"])
        self.assertEqual(depois["fid"], antes["fid"], "a rotação criou família nova")
        self.assertEqual(depois["family_started_at"], antes["family_started_at"],
                         "a rotação renovou o nascimento da família: a idade nunca venceria")

    def test_an_old_family_cannot_renew_itself(self):
        c = new_account("osc")
        _envelhecer_familia(c.user["id"], server()["state"].settings.session_absolute_ttl + 60)
        r = c.post("/v1/auth/refresh", {"refresh_token": c.refresh_token})
        self.assertEqual(r.status, 401, f"família vencida renovou: {r.body[:200]}")
        self.assertEqual(r.json["code"], "session_too_old")

    def test_an_old_family_is_revoked_entirely(self):
        """Revogar só a linha deixaria as irmãs vivas, e qualquer uma delas renovaria a árvore."""
        c = new_account("osc")
        _envelhecer_familia(c.user["id"], server()["state"].settings.session_absolute_ttl + 60)
        c.post("/v1/auth/refresh", {"refresh_token": c.refresh_token})
        with db_system() as d:
            vivas = d.scalar("SELECT count(*) FROM sessions WHERE user_id = $1"
                             "   AND revoked_at IS NULL", c.user["id"])
        self.assertEqual(int(vivas), 0, "sobrou sessão viva na família vencida")

    def test_the_access_token_stops_working_too(self):
        """Conferir só na renovação deixaria a sessão vencida valendo mais quinze minutos."""
        c = new_account("osc")
        self.assertEqual(c.get("/v1/me").status, 200)
        _envelhecer_familia(c.user["id"], server()["state"].settings.session_absolute_ttl + 60)
        self.assertEqual(c.get("/v1/me").status, 401,
                         "token de acesso de família vencida continuou valendo")

    def test_the_expiry_is_recorded_in_the_audit_trail(self):
        c = new_account("osc")
        _envelhecer_familia(c.user["id"], server()["state"].settings.session_absolute_ttl + 60)
        c.post("/v1/auth/refresh", {"refresh_token": c.refresh_token})
        with db_system() as d:
            self.assertTrue(d.scalar(
                "SELECT count(*) FROM audit_events WHERE actor_user_id = $1"
                "   AND action = 'auth.session_too_old'", c.user["id"]),
                "o vencimento da sessão não deixou trilha")


class AnIdleSessionExpiresTests(unittest.TestCase):

    def test_an_idle_session_cannot_renew_itself(self):
        c = new_account("osc")
        _tornar_inativa(c.user["id"], server()["state"].settings.session_idle_ttl + 60)
        r = c.post("/v1/auth/refresh", {"refresh_token": c.refresh_token})
        self.assertEqual(r.status, 401, f"sessão inativa renovou: {r.body[:200]}")
        self.assertEqual(r.json["code"], "session_idle")

    def test_an_idle_session_stops_answering(self):
        c = new_account("osc")
        _tornar_inativa(c.user["id"], server()["state"].settings.session_idle_ttl + 60)
        self.assertEqual(c.get("/v1/me").status, 401)

    def test_a_session_in_use_never_becomes_idle(self):
        """O uso renova a inatividade — senão a trava derrubaria quem está trabalhando."""
        c = new_account("osc")
        self.assertEqual(c.get("/v1/me").status, 200)
        _tornar_inativa(c.user["id"], server()["state"].settings.session_idle_ttl - 120)
        self.assertEqual(c.get("/v1/me").status, 200, "sessão em uso foi expirada por inatividade")
        with db_system() as d:
            inativa = d.scalar(
                "SELECT extract(epoch FROM now() - last_seen_at) FROM sessions"
                " WHERE user_id = $1 AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1",
                c.user["id"])
        self.assertLess(float(inativa), 120, "o uso não renovou last_seen_at")


class TheTwoLimitsAreConfigurationNotConstantsTests(unittest.TestCase):
    """E são LIDOS. `LOGIN_MAX_ATTEMPTS` existia na configuração e nenhum código a lia — operar a
    plataforma acreditando que uma variável de ambiente surte efeito é pior do que não tê-la."""

    def test_both_limits_are_read_from_settings(self):
        from pathlib import Path
        from tests.support import ROOT
        pkg = Path(ROOT) / "backend" / "impacto"
        for nome in ("session_absolute_ttl", "session_idle_ttl"):
            leitores = [f.name for f in pkg.rglob("*.py")
                        if f.name != "config.py" and nome in f.read_text(encoding="utf-8")]
            self.assertTrue(leitores, f"`{nome}` é configuração morta: ninguém a lê")

    def test_the_defaults_are_sane(self):
        s = server()["state"].settings
        self.assertGreater(s.session_absolute_ttl, s.access_token_ttl)
        self.assertGreater(s.session_absolute_ttl, s.session_idle_ttl,
                           "inatividade maior que idade máxima torna a idade inalcançável")


if __name__ == "__main__":
    unittest.main()
