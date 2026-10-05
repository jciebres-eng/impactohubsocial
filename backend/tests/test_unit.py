"""Testes unitários (sem banco): motores, segurança, adapters e validadores — com vetores oficiais quando existem."""
import base64
import hashlib
import hmac
import json
import socket
import struct
import threading
import time
import unittest
from datetime import date, datetime, timezone

from impacto.engines.match.engine import MatchInput, evaluate
from impacto.engines.match.territory import covers, specificity, valid
from impacto.engines.fiscal.engine import evaluate as fiscal
from impacto.engines.ai import local
from impacto.engines.ai.gateway import ExternalLLM, redact
from impacto.security import passwords, totp
from impacto.security.tokens import sign_payload, verify_payload
from impacto.security.crypto import FieldCipher, generate_key
from impacto.services.validators import cnpj_valid, cnpj_with_check_digits, safe_filename
from impacto.services.billing import stripe_signature_valid
from impacto.services import documents as docsvc
from impacto.adapters.storage import LocalStorage, sigv4_presign
from impacto.adapters.antivirus import ClamdAntivirus
from impacto.adapters.http_client import HttpClient
from impacto.http import ApiError

TODAY = date(2026, 10, 4)


def osc_call(**over):
    base = dict(org={"kind": "osc", "uf": "MT", "ibge_code": "5105259", "causes": ["educacao"], "founded_on": "2018-01-01",
                     "compliance_status": "approved", "certifications": []},
                call={"status": "open", "closes_at": "2026-12-01", "causes": ["educacao"], "territories": ["BR-MT"],
                      "ticket_min_cents": 100000, "ticket_max_cents": 2000000, "required_document_types": ["estatuto_social"]},
                project={"causes": ["educacao"], "territory": "BR-MT-5105259", "budget_total_cents": 500000, "milestones": []},
                documents=[{"doc_type": "estatuto_social", "status": "clean", "valid_until": None}], today=TODAY)
    for k, v in over.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    return evaluate(MatchInput.build("osc_call", **base))


def funder_project(**over):
    base = dict(org={"kind": "osc", "compliance_status": "approved", "founded_on": "2015-01-01"},
                funder={"causes": ["educacao"], "territories": ["BR-MT"], "ticket_min_cents": 100000, "ticket_max_cents": 1000000},
                project={"id": "p", "causes": ["educacao"], "territory": "BR-MT-5105259", "budget_total_cents": 800000, "visibility": "published",
                         "beneficiaries_count": 50, "urgency": "high", "indicators": [{"name": "x"}], "milestones": []},
                documents=[{"doc_type": d, "status": "clean", "valid_until": None} for d in ("estatuto_social", "cartao_cnpj", "ata_eleicao_diretoria", "cnd_federal")],
                today=TODAY)
    for k, v in over.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    return evaluate(MatchInput.build("funder_project", **base))


class MatchEngineTests(unittest.TestCase):
    def test_eligible_with_explanations(self):
        r = osc_call()
        self.assertEqual(r["eligibility"], "eligible")
        self.assertGreater(r["score"], 60)
        self.assertTrue(r["why_match"])
        self.assertEqual(r["next_action"]["code"], "start_application")
        for k in ("blockers", "requirements", "why_not", "risks", "missing_data", "signals", "engine_version", "weights_version"):
            self.assertIn(k, r)

    def test_hard_blockers(self):
        self.assertEqual(osc_call(call={"status": "closed"})["eligibility"], "blocked")
        self.assertEqual(osc_call(documents=[])["blockers"][0]["code"], "DOC_ESTATUTO_SOCIAL")
        self.assertEqual(osc_call(project={"territory": "BR-SP-3550308"})["eligibility"], "blocked")
        self.assertEqual(osc_call(org={"compliance_status": "rejected"})["eligibility"], "blocked")
        self.assertEqual(osc_call(org={"kind": "company"})["eligibility"], "blocked")
        r = osc_call(call={"min_org_age_months": 120})
        self.assertIn("ORG_AGE", [b["code"] for b in r["blockers"]])

    def test_expired_document_is_not_valid(self):
        r = osc_call(documents=[{"doc_type": "estatuto_social", "status": "clean", "valid_until": "2026-01-01"}])
        self.assertEqual(r["eligibility"], "blocked")
        r = osc_call(documents=[{"doc_type": "estatuto_social", "status": "pending_scan", "valid_until": None}])
        self.assertEqual(r["eligibility"], "blocked")

    def test_fractioning_allows_fit_via_milestone(self):
        r = osc_call(call={"ticket_max_cents": 300000}, project={"budget_total_cents": 900000, "milestones": [{"amount_cents": 250000}]})
        self.assertNotEqual(r["eligibility"], "blocked")
        self.assertIn("Marco 1", next(s for s in r["signals"] if s["key"] == "budget")["detail"])
        r = osc_call(call={"ticket_max_cents": 300000}, project={"budget_total_cents": 900000, "milestones": []})
        self.assertEqual(r["eligibility"], "blocked")

    def test_missing_data_lowers_confidence_and_never_invents_score(self):
        r = osc_call(org={"causes": [], "uf": None, "ibge_code": None}, project=None, call={"closes_at": None})
        self.assertIn("territory", [m["field"] for m in r["missing_data"]])
        self.assertLess(r["confidence"], osc_call()["confidence"])
        sparse = funder_project(project={"causes": [], "beneficiaries_count": None, "urgency": None, "indicators": []},
                                funder={"causes": [], "territories": []}, documents=[])
        self.assertIsNone(sparse["score"])
        self.assertEqual(sparse["recommended_state"], "revisao_humana")

    def test_funder_blockers(self):
        self.assertIn("CONFLICT_OF_INTEREST", [b["code"] for b in funder_project(conflict=True)["blockers"]])
        self.assertIn("EXCLUDED_CAUSE", [b["code"] for b in funder_project(funder={"excluded_causes": ["educacao"]})["blockers"]])
        self.assertIn("EXCLUDED_TERRITORY", [b["code"] for b in funder_project(funder={"excluded_territories": ["BR-MT"]})["blockers"]])
        self.assertIn("TICKET_INCOMPATIBLE", [b["code"] for b in funder_project(funder={"ticket_max_cents": 1000})["blockers"]])
        self.assertIn("MISSING_CRITICAL_DOCUMENT",
                      [b["code"] for b in funder_project(funder={"required_document_types": ["cebas"]})["blockers"]])
        self.assertEqual(funder_project()["eligibility"], "eligible")

    def test_plan_and_voucher_fields_are_ignored(self):
        a = funder_project()
        b = funder_project(org={"plan": "enterprise", "plan_key": "x", "voucher": "ABC"}, funder={"subscription": "premium"},
                           project={"boost": 100, "plan_key": "premium"})
        for k in ("score", "eligibility", "confidence", "signals"):
            self.assertEqual(a[k], b[k])

    def test_deterministic(self):
        a, b = funder_project(), funder_project()
        self.assertEqual(json.dumps(a, sort_keys=True, default=str), json.dumps(b, sort_keys=True, default=str))

    def test_custom_weights_versioned(self):
        r = osc_call(call={"weights": {"cause": 50, "hacker": 999}})
        self.assertIn("custom:cause=50", r["weights_version"])
        self.assertNotIn("hacker", r["weights_version"])

    def test_territory_codes(self):
        self.assertTrue(covers("BR", "BR-MT-5105259"))
        self.assertTrue(covers("BR-MT", "BR-MT-5105259"))
        self.assertFalse(covers("BR-SP", "BR-MT"))
        self.assertTrue(covers("INT", "PT"))
        self.assertEqual(specificity("BR-MT-5105259", "BR-MT-5105259"), 1.0)
        self.assertGreater(specificity("BR-MT", "BR-MT-5105259"), specificity("BR", "BR-MT-5105259"))
        self.assertFalse(valid("BR-MT-12"))


class FiscalEngineTests(unittest.TestCase):
    RULE = {"status": "approved", "code": "X", "version": "1", "name": "n", "mechanism": "m", "jurisdiction": "federal",
            "source_citation": "Lei X", "taxpayer_regimes": ["lucro_real"], "limit_pct": 1.0, "causes": ["criancas_adolescentes"],
            "effective_from": date(2020, 1, 1), "effective_to": None}

    def test_only_approved_and_current(self):
        self.assertEqual(fiscal([dict(self.RULE, status="draft")], {}, None)["items"], [])
        self.assertEqual(fiscal([dict(self.RULE, status="pending_review")], {}, None)["items"], [])
        self.assertEqual(fiscal([dict(self.RULE, effective_to=date(2021, 1, 1))], {}, None, ref=TODAY)["items"], [])
        self.assertEqual(len(fiscal([self.RULE], {}, None, ref=TODAY)["items"]), 1)

    def test_labels_and_estimate(self):
        r = fiscal([self.RULE], {"regime": "lucro_real", "estimated_ir_due_cents": 5_000_000}, {"causes": ["criancas_adolescentes"]}, ref=TODAY)
        it = r["items"][0]
        self.assertEqual(it["eligibility"]["status"], "provavel")
        self.assertEqual(it["estimate"]["max_deductible_cents"], 50_000)
        self.assertEqual((it["rule"]["label"], it["estimate"]["label"], it["professional_validation"]["required"]), ("REGRA", "ESTIMATIVA", True))

    def test_regime_mismatch_and_unknown(self):
        self.assertEqual(fiscal([self.RULE], {"regime": "simples"}, None, ref=TODAY)["items"][0]["eligibility"]["status"], "improvavel")
        self.assertEqual(fiscal([self.RULE], {}, None, ref=TODAY)["items"][0]["eligibility"]["status"], "indeterminada")

    def test_no_estimate_without_validated_limit(self):
        it = fiscal([dict(self.RULE, limit_pct=None)], {"regime": "lucro_real", "estimated_ir_due_cents": 100}, None, ref=TODAY)["items"][0]
        self.assertIsNone(it["estimate"])


class SecurityPrimitiveTests(unittest.TestCase):
    def test_totp_rfc6238_vectors(self):
        key = base64.b32encode(b"12345678901234567890").decode()
        for t, code in ((59, "94287082"), (1111111109, "07081804"), (1234567890, "89005924"), (2000000000, "69279037")):
            self.assertEqual(totp.hotp(totp._key(key), t // 30, 8), code)
        s = totp.new_secret()
        self.assertIsNotNone(totp.verify(s, totp.totp(s)))
        self.assertIsNone(totp.verify(s, "12345"))

    def test_password_hashing(self):
        h = passwords.hash_password("Senha-Forte-123")
        self.assertTrue(h.startswith("scrypt$"))
        self.assertTrue(passwords.verify_password("Senha-Forte-123", h))
        self.assertFalse(passwords.verify_password("senha-forte-123", h))
        self.assertFalse(passwords.verify_password("x", None))
        legacy = base64.urlsafe_b64encode(b"s" * 16 + hashlib.pbkdf2_hmac("sha256", b"Antiga-123", b"s" * 16, 210000)).decode()
        self.assertTrue(passwords.verify_password("Antiga-123", legacy))
        self.assertTrue(passwords.needs_rehash(legacy))
        self.assertTrue(passwords.password_problems("curta"))
        self.assertTrue(passwords.password_problems("aaaaaaaaaaaa"))

    def test_signed_tokens(self):
        t = sign_payload("k" * 40, {"d": "1"}, 60)
        self.assertEqual(verify_payload("k" * 40, t)["d"], "1")
        self.assertIsNone(verify_payload("outra" * 10, t))
        self.assertIsNone(verify_payload("k" * 40, sign_payload("k" * 40, {"d": "1"}, -1)))
        self.assertIsNone(verify_payload("k" * 40, t[:-1] + ("1" if t[-1] == "0" else "0")))

    def test_field_encryption_and_rotation(self):
        k1, k2 = generate_key(), generate_key()
        token = FieldCipher(k1).encrypt("segredo")
        self.assertEqual(FieldCipher(f"{k2},{k1}").decrypt(token), "segredo")
        with self.assertRaises(ValueError):
            FieldCipher(k2).decrypt(token)

    def test_stripe_signature(self):
        body, secret, t = b'{"id":"evt"}', "whsec_x", int(time.time())
        sig = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
        self.assertTrue(stripe_signature_valid(body, f"t={t},v1={sig}", secret))
        self.assertFalse(stripe_signature_valid(body + b" ", f"t={t},v1={sig}", secret))
        self.assertFalse(stripe_signature_valid(body, f"t={t - 1000},v1={sig}", secret))
        self.assertFalse(stripe_signature_valid(body, "lixo", secret))

    def test_pii_redaction(self):
        txt, n = redact("CPF 123.456.789-09, email ana@x.org, tel (65) 99999-1234, CEP 78455-000")
        for leak in ("123.456.789-09", "ana@x.org", "99999-1234", "78455-000"):
            self.assertNotIn(leak, txt)
        self.assertEqual(n, 4)


class ValidatorAndUploadTests(unittest.TestCase):
    def test_cnpj(self):
        self.assertTrue(cnpj_valid("11.222.333/0001-81"))
        self.assertFalse(cnpj_valid("11.222.333/0001-82"))
        self.assertFalse(cnpj_valid("00000000000000"))
        self.assertTrue(cnpj_valid(cnpj_with_check_digits("123456780001")))

    def test_safe_filename(self):
        self.assertEqual(safe_filename("../../etc/passwd"), "passwd")
        self.assertEqual(safe_filename("C:\\Windows\\a.pdf"), "a.pdf")
        self.assertEqual(safe_filename("relatório final.pdf"), "relatorio final.pdf")

    def test_sniffing(self):
        self.assertEqual(docsvc.sniff("a.pdf", b"%PDF-1.7 ..."), "application/pdf")
        self.assertEqual(docsvc.sniff("a.png", b"\x89PNG\r\n\x1a\n...."), "image/png")
        for name, data, code in (("a.pdf", b"MZ....", "content_mismatch"), ("a.svg", b"<svg/>", "file_type_not_allowed"),
                                 ("a.txt", b"\x00\x01", "content_mismatch"), ("a.png", b"", "empty_file")):
            with self.assertRaises(ApiError) as cm:
                docsvc.sniff(name, data)
            self.assertEqual(cm.exception.code, code)

    def test_local_storage_blocks_traversal(self):
        import tempfile
        st = LocalStorage(tempfile.mkdtemp())
        st.put("org/abc", b"x", "text/plain")
        self.assertEqual(st.get("org/abc"), b"x")
        with self.assertRaises(ValueError):
            st.get("../../etc/passwd")


class AdapterTests(unittest.TestCase):
    def test_sigv4_official_aws_vector(self):
        qs = sigv4_presign("GET", "examplebucket.s3.amazonaws.com", "/test.txt", "us-east-1", "AKIAIOSFODNN7EXAMPLE",
                           "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", 86400, datetime(2013, 5, 24, tzinfo=timezone.utc))
        self.assertTrue(qs.endswith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"))

    def _fake_clamd(self, reply: bytes):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        received = {}

        def run():
            conn, _ = srv.accept()
            buf = b""
            while not buf.endswith(struct.pack(">I", 0)):
                buf += conn.recv(65536)
            received["data"] = buf
            conn.sendall(reply + b"\0")
            conn.close()
            srv.close()
        threading.Thread(target=run, daemon=True).start()
        return srv.getsockname()[1], received

    def test_clamd_protocol(self):
        port, rec = self._fake_clamd(b"stream: OK")
        self.assertEqual(ClamdAntivirus("127.0.0.1", port).scan(b"conteudo")[0], "clean")
        self.assertTrue(rec["data"].startswith(b"zINSTREAM\0"))
        port, _ = self._fake_clamd(b"stream: Eicar-Test-Signature FOUND")
        self.assertEqual(ClamdAntivirus("127.0.0.1", port).scan(b"X5O!P%@AP")[0], "infected")

    def test_http_client_retries(self):
        calls = []

        def transport(m, u, h, b, t):
            calls.append(1)
            return (503, {}, b"") if len(calls) < 3 else (200, {}, b"ok")
        self.assertEqual(HttpClient(transport, retries=2, backoff=0).request("GET", "https://x")[2], b"ok")
        self.assertEqual(len(calls), 3)

    def test_external_llm_adapters(self):
        seen = {}

        def anthropic(m, u, h, b, t):
            seen.update(url=u, headers=h, body=json.loads(b))
            return 200, {}, json.dumps({"content": [{"type": "text", "text": "ok"}], "usage": {"input_tokens": 5, "output_tokens": 1}}).encode()
        llm = ExternalLLM("anthropic", "", "sk-test", "modelo-configurado", 5, HttpClient(anthropic, retries=0))
        text, meta = llm.complete("sys", "user")
        self.assertEqual((text, meta["tokens_in"]), ("ok", 5))
        self.assertEqual(seen["url"], "https://api.anthropic.com/v1/messages")
        self.assertEqual(seen["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(seen["body"]["model"], "modelo-configurado")

        def openai(m, u, h, b, t):
            return 200, {}, json.dumps({"choices": [{"message": {"content": "oi"}}], "usage": {"prompt_tokens": 3}}).encode()
        self.assertEqual(ExternalLLM("openai_compatible", "https://llm.local", "k", "m", 5, HttpClient(openai, retries=0)).complete("s", "u")[0], "oi")


class LocalAiTests(unittest.TestCase):
    def test_structure_need(self):
        r = local.structure_need("Comprar 20 cestas básicas a R$ 150,00 cada para 20 famílias em situação de vulnerabilidade.")
        self.assertEqual(r["budget_items"][0]["total_cents"], 300000)
        self.assertEqual(r["beneficiaries_count"], 20)
        self.assertIn("seguranca_alimentar", r["causes"])
        self.assertIn(2, r["ods"])

    def test_draft_marks_gaps_and_never_invents(self):
        txt = local.draft_document("project_proposal", {"title": "T", "territory": "BR-MT"}, {"legal_name": "OSC"}, None, [], [])
        self.assertIn("[COMPLETAR: descrição do problema", txt)
        self.assertIn("validação de profissional habilitado", txt)

    def test_classify_document(self):
        r = local.classify_document("CERTIDÃO NEGATIVA DE DÉBITOS RELATIVOS AOS TRIBUTOS FEDERAIS E À DÍVIDA ATIVA DA UNIÃO ... Válida até 31/12/2026", "cnd.pdf")
        self.assertEqual(r["suggested_type"], "cnd_federal")
        self.assertEqual(r["valid_until"], "2026-12-31")


class SsrfTests(unittest.TestCase):
    def setUp(self):
        import os
        self._old = os.environ.get("IMPACTO_ENV")

    def tearDown(self):
        import os
        if self._old is None:
            os.environ.pop("IMPACTO_ENV", None)
        else:
            os.environ["IMPACTO_ENV"] = self._old

    def test_internal_destinations_are_blocked(self):
        import os
        from impacto.adapters.http_client import check_destination
        os.environ["IMPACTO_ENV"] = "production"
        for url in ("http://example.com/x", "https://169.254.169.254/latest/meta-data", "https://10.0.0.5/", "https://192.168.1.1/",
                    "https://127.0.0.1/", "https://[::1]/", "https://0.0.0.0/"):
            with self.assertRaises(ValueError, msg=url):
                check_destination(url)

    def test_loopback_http_only_in_dev_and_redirects_not_followed(self):
        import http.server
        import os
        from impacto.adapters.http_client import HttpClient

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/")
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            os.environ["IMPACTO_ENV"] = "test"
            st, _, _ = HttpClient(retries=0).request("GET", f"http://127.0.0.1:{srv.server_port}/")
            self.assertEqual(st, 302)   # redirecionamento devolvido, não seguido
            os.environ["IMPACTO_ENV"] = "production"
            with self.assertRaises(ValueError):
                HttpClient(retries=0).request("GET", f"http://127.0.0.1:{srv.server_port}/")
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
