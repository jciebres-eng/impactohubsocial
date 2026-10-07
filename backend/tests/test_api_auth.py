"""Autenticação e sessão — positivos e NEGATIVOS (enumeração, brute force, tokens expirados/revogados, CSRF, MFA)."""
import os
import unittest
import uuid

from tests.support import PASSWORD, Client, db_system, last_token_for, new_account, next_cnpj, server


class AuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()

    def test_register_verify_login_me(self):
        c = new_account("osc")
        me = c.get("/v1/me").json
        self.assertTrue(me["user"]["email_verified"])
        self.assertEqual(me["active_org"]["role"], "owner")
        self.assertIn("osc_basic", me["entitlements"]["plans"])

    def test_register_does_not_enumerate_existing_email(self):
        c = new_account("osc")
        r = Client().post("/v1/auth/register", {"email": c.email, "password": PASSWORD, "full_name": "Xavier", "accept_terms": True})
        self.assertEqual(r.status, 202)
        r2 = Client().post("/v1/auth/register", {"email": f"novo-{uuid.uuid4().hex[:6]}@t.org", "password": PASSWORD, "full_name": "Yara",
                                                  "accept_terms": True})
        self.assertEqual(r.json, r2.json)

    def test_login_errors_are_identical(self):
        c = new_account("osc")
        a = Client().post("/v1/auth/login", {"email": c.email, "password": "senha-errada-123"})
        b = Client().post("/v1/auth/login", {"email": "ninguem-" + uuid.uuid4().hex + "@t.org", "password": "senha-errada-123"})
        self.assertEqual((a.status, a.json["code"], a.json["title"]), (b.status, b.json["code"], b.json["title"]))

    def test_weak_password_and_invalid_cnpj_rejected(self):
        r = Client().post("/v1/auth/register", {"email": f"w{uuid.uuid4().hex[:6]}@t.org", "password": "123", "full_name": "W", "accept_terms": True})
        self.assertEqual(r.status, 422)
        r = Client().post("/v1/auth/register", {"email": f"w{uuid.uuid4().hex[:6]}@t.org", "password": PASSWORD, "full_name": "W", "accept_terms": True,
                                                "organization": {"kind": "osc", "legal_name": "OSC X", "cnpj": "11111111111111"}})
        self.assertEqual(r.status, 422)
        r = Client().post("/v1/auth/register", {"email": f"w{uuid.uuid4().hex[:6]}@t.org", "password": PASSWORD, "full_name": "W", "accept_terms": False})
        self.assertEqual(r.status, 422)

    def test_unknown_fields_rejected(self):
        r = Client().post("/v1/auth/login", {"email": "a@b.org", "password": "x", "is_platform_admin": True})
        self.assertEqual(r.status, 422)

    def test_bruteforce_lockout(self):
        c = new_account("osc")
        for _ in range(8):
            Client().post("/v1/auth/login", {"email": c.email, "password": "errada-errada-1"})
        r = Client().post("/v1/auth/login", {"email": c.email, "password": PASSWORD})
        self.assertEqual(r.status, 429)
        self.assertEqual(r.json["code"], "account_locked")

    def test_ip_rate_limit(self):
        old = os.environ["RATE_LIMIT_MULTIPLIER"]
        os.environ["RATE_LIMIT_MULTIPLIER"] = "1"
        try:
            with db_system() as d:
                d.run("DELETE FROM rate_events WHERE bucket = 'forgot_ip'")
            codes = [Client().post("/v1/auth/forgot-password", {"email": "x@y.org"}).status for _ in range(6)]
            self.assertEqual(codes[:5], [202] * 5)
            self.assertEqual(codes[5], 429)
        finally:
            os.environ["RATE_LIMIT_MULTIPLIER"] = old
            with db_system() as d:
                d.run("DELETE FROM rate_events WHERE bucket = 'forgot_ip'")

    def test_refresh_rotation_and_reuse_detection(self):
        c = new_account("osc")
        old_refresh = c.refresh_token
        r = c.post("/v1/auth/refresh", {"refresh_token": old_refresh})
        self.assertEqual(r.status, 200)
        new_refresh = r.json["refresh_token"]
        c._absorb(r.json)
        self.assertEqual(c.get("/v1/me").status, 200)
        # reuso do token antigo ⇒ família inteira revogada
        self.assertEqual(Client().post("/v1/auth/refresh", {"refresh_token": old_refresh}).json["code"], "refresh_reuse")
        self.assertEqual(Client().post("/v1/auth/refresh", {"refresh_token": new_refresh}).status, 401)
        self.assertEqual(c.get("/v1/me").status, 401)

    def test_logout_revokes_session(self):
        c = new_account("osc")
        self.assertEqual(c.post("/v1/auth/logout").status, 204)
        self.assertEqual(c.get("/v1/me").status, 401)

    def test_expired_access_token(self):
        c = new_account("osc")
        with db_system() as d:
            d.run("UPDATE sessions SET access_expires_at = now() - interval '1 second' WHERE user_id = $1", c.user["id"])
        self.assertEqual(c.get("/v1/me").status, 401)

    def test_disabled_user_loses_access(self):
        c = new_account("osc")
        with db_system() as d:
            d.run("UPDATE users SET status = 'disabled' WHERE id = $1", c.user["id"])
        self.assertEqual(c.get("/v1/me").status, 401)

    def test_cookie_mode_requires_csrf(self):
        c = new_account("osc", mode="cookie")
        self.assertEqual(c.get("/v1/me").status, 200)
        r = c.request("PATCH", "/v1/org", {"description": "x"}, headers={"X-CSRF-Token": "forjado"})
        self.assertEqual((r.status, r.json["code"]), (403, "csrf"))
        c2 = Client("cookie")
        c2.jar, c2.opener = c.jar, c.opener
        r = c2.request("PATCH", "/v1/org", {"description": "x"})
        self.assertEqual(r.json["code"], "csrf")
        self.assertEqual(c.patch("/v1/org", {"description": "Descrição válida"}).status, 200)

    def test_foreign_origin_blocked(self):
        c = new_account("osc")
        r = c.request("PATCH", "/v1/org", {"description": "x"}, headers={"Origin": "https://atacante.example"})
        self.assertEqual((r.status, r.json["code"]), (403, "bad_origin"))

    def test_unverified_email_blocks_writes(self):
        c = new_account("osc", verify=False)
        r = c.post("/v1/projects", {"title": "Projeto", "territory": "BR-MT"})
        self.assertEqual((r.status, r.json["code"]), (403, "email_not_verified"))
        self.assertEqual(c.get("/v1/projects").status, 200)

    def test_mfa_flow_and_recovery_code(self):
        """v0.23.0 — cada passo usa um código NOVO, porque o código agora é queimado.

        Até esta versão o teste reusava o mesmo código de seis dígitos em `mfa/enable` e em
        `mfa/verify` — e passava, porque o reuso era possível. Era o defeito encontrando o teste:
        `totp.verify()` devolvia o contador aceito com o comentário "para impedir reuso" e nenhum
        dos quatro chamadores o guardava. Agora cada etapa avança o passo, como uma pessoa faz
        quando espera o código seguinte.
        """
        import time as _t
        from impacto.security import totp
        c = new_account("osc")
        secret = c.post("/v1/auth/mfa/setup").json["secret"]
        self.assertEqual(c.post("/v1/auth/mfa/enable", {"code": "000000"}).status, 400)
        agora = _t.time()
        r = c.post("/v1/auth/mfa/enable", {"code": totp.totp(secret, at=agora)})
        codes = r.json["recovery_codes"]
        x = Client()
        r = x.post("/v1/auth/login", {"email": c.email, "password": PASSWORD})
        self.assertTrue(r.json["mfa_required"])
        self.assertNotIn("access_token", r.json)
        self.assertEqual(x.post("/v1/auth/mfa/verify", {"mfa_token": r.json["mfa_token"], "code": "123456"}).status, 401)
        ok = x.post("/v1/auth/mfa/verify", {"mfa_token": r.json["mfa_token"],
                                            "code": totp.totp(secret, at=agora + 30)})
        self.assertEqual(ok.status, 200)
        y = Client()
        r = y.post("/v1/auth/login", {"email": c.email, "password": PASSWORD})
        self.assertEqual(y.post("/v1/auth/mfa/verify", {"mfa_token": r.json["mfa_token"], "recovery_code": codes[0]}).status, 200)
        r = Client().post("/v1/auth/login", {"email": c.email, "password": PASSWORD})
        self.assertEqual(Client().post("/v1/auth/mfa/verify", {"mfa_token": r.json["mfa_token"], "recovery_code": codes[0]}).status, 401)

    def test_the_same_totp_code_never_works_twice(self):
        """Replay de código TOTP — encontrado por auditoria independente.

        `security/totp.py::verify()` devolvia o contador aceito desde sempre, com o docstring
        dizendo "para impedir reuso", e **nenhum dos quatro chamadores o guardava**. Com janela de
        ±1 passo, o mesmo código de seis dígitos valia cerca de 90 segundos e podia ser
        reapresentado. Quem o lê por cima do ombro, ou o captura numa página falsa, o usa de novo.
        """
        import time as _t
        from impacto.security import totp
        c = new_account("osc")
        secret = c.post("/v1/auth/mfa/setup").json["secret"]
        agora = _t.time()
        self.assertEqual(c.post("/v1/auth/mfa/enable", {"code": totp.totp(secret, at=agora)}).status, 200)

        codigo = totp.totp(secret, at=agora + 30)
        primeiro = Client()
        r = primeiro.post("/v1/auth/login", {"email": c.email, "password": PASSWORD})
        self.assertEqual(primeiro.post("/v1/auth/mfa/verify",
                                       {"mfa_token": r.json["mfa_token"], "code": codigo}).status, 200)

        # O MESMO código, no mesmo passo de tempo, num desafio novo: tem de falhar.
        segundo = Client()
        r2 = segundo.post("/v1/auth/login", {"email": c.email, "password": PASSWORD})
        reuso = segundo.post("/v1/auth/mfa/verify",
                             {"mfa_token": r2.json["mfa_token"], "code": codigo})
        self.assertEqual(reuso.status, 401, f"o código foi aceito duas vezes: {reuso.body[:200]}")
        self.assertEqual(reuso.json["code"], "invalid_mfa_code")

    def test_the_counter_cannot_be_moved_backwards_even_by_the_database_owner(self):
        """A segunda trava: o gatilho recusa regredir o contador.

        Uma via de verificação futura que esquecesse de gravar o contador não conseguiria, nem por
        engano, voltar atrás e reaceitar um código já usado.
        """
        import time as _t
        from impacto.security import totp
        from tests.support import db_system, owner_conn
        c = new_account("osc")
        secret = c.post("/v1/auth/mfa/setup").json["secret"]
        c.post("/v1/auth/mfa/enable", {"code": totp.totp(secret, at=_t.time())})
        with db_system() as d:
            contador = d.scalar("SELECT mfa_last_counter FROM users WHERE id = $1", c.user["id"])
        self.assertIsNotNone(contador, "o contador do código aceito não foi gravado")
        conn = owner_conn()
        try:
            with self.assertRaises(Exception) as cm:
                conn.run("UPDATE users SET mfa_last_counter = $2 WHERE id = $1",
                         c.user["id"], int(contador) - 5)
            self.assertIn("não retrocede", str(cm.exception))
        finally:
            conn.close()

    def test_password_reset_revokes_sessions(self):
        c = new_account("osc")
        self.assertEqual(Client().post("/v1/auth/forgot-password", {"email": c.email}).status, 202)
        tok = last_token_for(c.email, "/redefinir-senha")
        self.assertEqual(Client().post("/v1/auth/reset-password", {"token": tok, "password": "Nova-Senha-Muito-Forte-9"}).status, 200)
        self.assertEqual(c.get("/v1/me").status, 401)
        self.assertEqual(Client().post("/v1/auth/reset-password", {"token": tok, "password": "Outra-Senha-Forte-77"}).status, 400)
        self.assertEqual(Client().login(c.email, "Nova-Senha-Muito-Forte-9").status, 200)

    def test_sessions_list_and_revoke_other(self):
        c = new_account("osc")
        other = Client()
        other.login(c.email, PASSWORD)
        items = c.get("/v1/auth/sessions").json["items"]
        target = next(s for s in items if not s["current"])
        self.assertEqual(c.delete(f"/v1/auth/sessions/{target['id']}").status, 204)
        self.assertEqual(other.get("/v1/me").status, 401)

    def test_invitation_flow_and_role_limits(self):
        owner = new_account("osc")
        em = f"conv-{uuid.uuid4().hex[:6]}@t.org"
        self.assertEqual(owner.post("/v1/org/invitations", {"email": em, "role": "analyst"}).status, 201)
        tok = last_token_for(em, "/convite")
        m = Client()
        m.post("/v1/auth/register", {"email": em, "password": PASSWORD, "full_name": "Membro", "accept_terms": True})
        m.login(em, PASSWORD)
        r = m.post("/v1/auth/accept-invite", {"token": tok})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(m.get("/v1/me").json["active_org"]["role"], "analyst")
        # analista não convida nem altera papéis
        self.assertEqual(m.post("/v1/org/invitations", {"email": "x@t.org", "role": "viewer"}).status, 403)
        self.assertEqual(m.patch(f"/v1/org/members/{owner.user['id']}", {"role": "viewer"}).status, 403)
        # convite não pode ser aceito por outro e-mail
        em2 = f"conv2-{uuid.uuid4().hex[:6]}@t.org"
        owner.post("/v1/org/invitations", {"email": em2, "role": "viewer"})
        intruder = new_account("osc")
        self.assertEqual(intruder.post("/v1/auth/accept-invite", {"token": last_token_for(em2, "/convite")}).json["code"], "invite_email_mismatch")

    def test_cnpj_uniqueness(self):
        cnpj = next_cnpj()
        body = lambda e: {"email": e, "password": PASSWORD, "full_name": "Alice", "accept_terms": True,
                          "organization": {"kind": "osc", "legal_name": "OSC Dup", "cnpj": cnpj}}
        self.assertEqual(Client().post("/v1/auth/register", body(f"a{uuid.uuid4().hex[:5]}@t.org")).status, 202)
        self.assertEqual(Client().post("/v1/auth/register", body(f"b{uuid.uuid4().hex[:5]}@t.org")).status, 409)


if __name__ == "__main__":
    unittest.main()
