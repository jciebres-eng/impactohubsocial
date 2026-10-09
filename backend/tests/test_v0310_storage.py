"""v0.31.0 — armazenamento para o Cloudflare R2 e verificação do adaptador S3 contra servidor real.

Duas camadas:
  - unitária (sempre roda): a configuração recusa região AWS com endpoint R2 e http em produção;
    armazenamento local sem volume declarado aparece como NÃO durável;
  - protocolo (roda quando há S3_TEST_ENDPOINT): `scripts/storage_smoke.py` contra um servidor S3 que
    VALIDA assinatura (MinIO no job `armazenamento` do CI). Sem servidor, pula dizendo por quê — pular
    não é passar.
"""
from __future__ import annotations

import importlib.util
import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from impacto import config as C

ROOT = Path(__file__).resolve().parents[2]


def _base(**kw):
    # Ambiente mínimo de desenvolvimento: só o que `load_settings` exige; o campo sob teste vem em **kw.
    with mock.patch.dict(os.environ, {"IMPACTO_ENV": "development", "DATABASE_URL": "postgresql://u@h/d",
                                      "STORAGE_PROVIDER": "local"}):
        s = C.load_settings()
    return replace(s, **kw)


class R2ConfigTests(unittest.TestCase):
    def test_r2_endpoint_is_recognised(self):
        self.assertTrue(C.is_r2_endpoint("https://abc123.r2.cloudflarestorage.com"))
        self.assertTrue(C.is_r2_endpoint("https://abc123.eu.r2.cloudflarestorage.com"))
        self.assertFalse(C.is_r2_endpoint("https://s3.sa-east-1.amazonaws.com"))
        self.assertFalse(C.is_r2_endpoint("https://r2.cloudflarestorage.com.evil.example"))
        self.assertFalse(C.is_r2_endpoint(""))

    def _errors(self, **kw) -> str:
        s = _base(storage_provider="s3", s3_bucket="b", s3_access_key_id="k", s3_secret_access_key="s", **kw)
        try:
            C.validate(s)
        except C.ConfigError as e:
            return str(e)
        return ""

    def test_r2_with_aws_region_is_refused(self):
        self.assertIn("S3_REGION deve ser `auto`", self._errors(s3_endpoint="https://abc.r2.cloudflarestorage.com", s3_region="sa-east-1"))

    def test_r2_with_auto_or_alias_is_accepted(self):
        for region in ("auto", "us-east-1", ""):
            self.assertNotIn("S3_REGION", self._errors(s3_endpoint="https://abc.r2.cloudflarestorage.com", s3_region=region))

    def test_aws_endpoint_keeps_its_region(self):
        self.assertNotIn("S3_REGION", self._errors(s3_endpoint="", s3_region="sa-east-1"))

    def test_env_example_documents_r2(self):
        ex = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("r2.cloudflarestorage.com", ex)
        self.assertIn("S3_REGION=auto", ex)


class EphemeralStorageTests(unittest.TestCase):
    def test_local_storage_in_production_without_volume_is_not_durable(self):
        s = _base(env="production", storage_provider="local")
        with mock.patch.dict(os.environ, {"STORAGE_LOCAL_PERSISTENT": "false"}):
            self.assertTrue(C.storage_is_ephemeral(s))
        with mock.patch.dict(os.environ, {"STORAGE_LOCAL_PERSISTENT": "true"}):
            self.assertFalse(C.storage_is_ephemeral(s))

    def test_s3_and_development_are_not_flagged(self):
        self.assertFalse(C.storage_is_ephemeral(_base(env="production", storage_provider="s3")))
        self.assertFalse(C.storage_is_ephemeral(_base(env="development", storage_provider="local")))


@unittest.skipUnless(os.getenv("S3_TEST_ENDPOINT"), "sem servidor S3 de teste (S3_TEST_ENDPOINT) — roda no job `armazenamento` do CI")
class RealS3ProtocolTests(unittest.TestCase):
    def test_adapter_against_signature_validating_server(self):
        spec = importlib.util.spec_from_file_location("storage_smoke", ROOT / "scripts" / "storage_smoke.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        from impacto.adapters.storage import S3Storage
        st = S3Storage(os.environ["S3_TEST_ENDPOINT"], os.getenv("S3_TEST_REGION", "us-east-1"), os.environ["S3_TEST_BUCKET"],
                       os.environ["S3_TEST_ACCESS_KEY_ID"], os.environ["S3_TEST_SECRET_ACCESS_KEY"])
        mod.create_bucket(st)
        res = {r["check"]: r for r in mod.run(st)}
        for check in ("put", "get_same_bytes", "presigned_get_without_credentials", "expired_presigned_refused",
                      "tampered_signature_refused", "wrong_secret_refused", "delete_removes"):
            self.assertIn(check, res, f"verificação não executada: {check}")
            self.assertTrue(res[check]["passed"], f"{check}: {res[check]['detail']}")
        self.assertNotIn("unexpected_error", res, res.get("unexpected_error"))


if __name__ == "__main__":
    unittest.main()
