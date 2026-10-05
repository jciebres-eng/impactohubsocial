"""SSO OIDC contra um IdP falso local (discovery, JWKS e token endpoint reais via HTTP) com chave RSA gerada no teste."""
import json
import threading
import time
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from tests.support import Client, server


class FakeIdP:
    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.claims_override = {}
        idp = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, obj, code=200):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                if self.path.startswith("/.well-known/openid-configuration"):
                    return self._json({"issuer": idp.issuer, "authorization_endpoint": idp.issuer + "/authorize",
                                       "token_endpoint": idp.issuer + "/token", "jwks_uri": idp.issuer + "/jwks"})
                if self.path.startswith("/jwks"):
                    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(idp.key.public_key()))
                    jwk.update({"kid": "k1", "use": "sig", "alg": "RS256"})
                    return self._json({"keys": [jwk]})
                self._json({}, 404)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                form = urllib.parse.parse_qs(self.rfile.read(n).decode())
                idp.last_token_request = form
                now = int(time.time())
                claims = {"iss": idp.issuer, "aud": "client-impacto", "sub": "user-123", "iat": now, "exp": now + 300,
                          "nonce": idp.nonce, "email": "sso.user@empresa.com", "email_verified": True, "name": "Usuária SSO", "amr": ["pwd", "mfa"]}
                claims.update(idp.claims_override)
                tok = jwt.encode(claims, idp.key, algorithm="RS256", headers={"kid": "k1"})
                return self._json({"id_token": tok, "access_token": "x", "token_type": "Bearer"})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.issuer = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


class OidcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.st = server()["state"]
        cls.idp = FakeIdP()
        s = cls.st.settings
        cls.old = (s.oidc_issuer, s.oidc_client_id, s.oidc_client_secret, s.oidc_redirect_uri)
        s.oidc_issuer, s.oidc_client_id, s.oidc_client_secret = cls.idp.issuer, "client-impacto", "segredo"
        s.oidc_redirect_uri = "http://testserver.local/v1/auth/oidc/callback"

    @classmethod
    def tearDownClass(cls):
        s = cls.st.settings
        s.oidc_issuer, s.oidc_client_id, s.oidc_client_secret, s.oidc_redirect_uri = cls.old

    def _start(self, c):
        import urllib.request

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(c.jar))
        try:
            opener.open(c.base + "/v1/auth/oidc/start?redirect=/painel")
        except urllib.error.HTTPError as e:
            loc = e.headers["Location"]
        q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
        self.assertEqual(q["code_challenge_method"], ["S256"])
        self.idp.nonce = q["nonce"][0]
        return q["state"][0], opener

    def _callback(self, c, opener, state):
        try:
            opener.open(c.base + f"/v1/auth/oidc/callback?code=abc&state={state}")
        except urllib.error.HTTPError as e:
            return e
        raise AssertionError("esperava redirecionamento")

    def test_sso_login_provisions_user_and_session(self):
        c = Client("cookie")
        state, opener = self._start(c)
        r = self._callback(c, opener, state)
        self.assertEqual((r.code, r.headers["Location"]), (302, "/painel"))
        self.assertIn("code_verifier", self.idp.last_token_request)
        me = c.get("/v1/me").json
        self.assertEqual(me["user"]["email"], "sso.user@empresa.com")
        self.assertTrue(me["user"]["mfa_verified"])
        # state não pode ser reutilizado
        self.assertEqual(self._callback(Client("cookie"), opener, state).code, 400)

    def test_rejects_wrong_audience_nonce_and_unverified_email(self):
        for override, code in (({"aud": "outro-cliente"}, "oidc_invalid_token"), ({"nonce": "forjado"}, "oidc_nonce_mismatch"),
                               ({"email_verified": False}, "oidc_email_unverified"), ({"exp": int(time.time()) - 3600}, "oidc_invalid_token")):
            self.idp.claims_override = override
            c = Client("cookie")
            state, _ = self._start(c)
            if "nonce" in override:
                pass
            r = c.get(f"/v1/auth/oidc/callback?code=abc&state={state}")
            self.assertEqual(r.json["code"], code, override)
        self.idp.claims_override = {}
